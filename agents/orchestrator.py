"""Orchestrator — end-to-end pipeline coordinator.

Runs the full pipeline:
  1. Parse requirements   (DeepSeek Agent)
  2. Design blueprint     (DeepSeek Agent + deterministic clock solver)
  3. Validate blueprint   (deterministic)
  4. Scaffold project     (deterministic — HAL download + file copy)
  5. Generate init code   (deterministic — cookbook recipes)
  6. Generate app logic   (DeepSeek Agent)
  7. Validate identifiers (deterministic)
  8. Inject user code     (deterministic)
  9. Build + fix loop     (GCC + DeepSeek fixes)
"""

from __future__ import annotations
import logging
import re
import yaml
from pathlib import Path

from agents.agent_base import DeepSeekClient
from agents.requirement_parser import RequirementParserAgent
from agents.architect import ArchitectAgent
from agents.code_generator import CodeGeneratorAgent
from agents.build_agent import BuildAgent

from core.project_builder import ProjectBuilder
from core.clock_engine import ClockEngine
from core.peripheral_engine import PeripheralEngine
from core.gpio_engine import GPIOEngine
from core.makefile_generator import MakefileGenerator
from core.linker_generator import LinkerGenerator
from core.hal_conf_generator import HALConfGenerator
from core.startup_manager import StartupManager

from database.mcu.stm32f446re import get_stm32f446re_profile
from database.templates.main_c import generate_main_c
from database.templates.main_h import generate_main_h
from database.templates.it_c import generate_it_c
from database.templates.hal_msp_c import generate_hal_msp_c

from hal_manager.cache import HALCache
from hal_manager.extractor import HALExtractor

from validation.clock_validator import ClockValidator
from validation.pin_conflict_validator import PinConflictValidator
from validation.peripheral_validator import PeripheralValidator
from validation.identifier_validator import IdentifierValidator
from validation.requirements_verifier import RequirementsVerifier

from schemas.requirements import PipelineResult

log = logging.getLogger(__name__)


class Orchestrator:
    """Top-level pipeline coordinator."""

    def __init__(self, config_path: str = "config.yaml", mcu_name: str = "STM32F446RETx",
                 output_dir: str = "./generated"):
        self.config = self._load_config(config_path)
        self.output_dir = output_dir
        self.mcu_name = mcu_name

        # Load MCU profile
        if mcu_name == "STM32F446RETx":
            self.mcu = get_stm32f446re_profile()
        else:
            raise ValueError(f"Unsupported MCU: {mcu_name}. Only STM32F446RETx supported.")

        # Initialize DeepSeek client
        ds_cfg = self.config.get("deepseek", {})
        self.client = DeepSeekClient(
            api_key=None,  # reads from env
            model=ds_cfg.get("model", "deepseek-reasoner"),
        )

        # Initialize agents
        self.parser = RequirementParserAgent(self.client, self.mcu)
        self.architect = ArchitectAgent(self.client, self.mcu)
        self.code_gen = CodeGeneratorAgent(self.client)
        self.build_agent = BuildAgent(
            self.client,
            max_attempts=self.config.get("build", {}).get("max_compile_fix_attempts", 5),
        )

    async def run(self, requirements: str) -> PipelineResult:
        """Execute the full pipeline."""
        stages_completed = []

        try:
            # --- Stage 1: Parse requirements ---
            log.info("=== Stage 1: Parsing requirements ===")
            spec = self.parser.parse(requirements)
            stages_completed.append("parse_requirements")

            # --- Stage 2: Design blueprint ---
            log.info("=== Stage 2: Designing blueprint ===")
            blueprint = self.architect.design(spec)
            stages_completed.append("design_blueprint")

            # --- Stage 3: Validate blueprint ---
            log.info("=== Stage 3: Validating blueprint ===")
            self._validate_blueprint(blueprint)
            stages_completed.append("validate_blueprint")

            # --- Stage 4: Scaffold project ---
            log.info("=== Stage 4: Scaffolding project ===")
            builder = ProjectBuilder(
                hal_cache_dir=self.config.get("hal", {}).get("cache_dir", "~/.stm32_hal_cache")
            )
            project_dir = builder.build(blueprint, self.output_dir)

            # Save blueprint for emulation test stage
            import json as _json
            bp_path = project_dir / "blueprint.json"
            bp_path.write_text(
                _json.dumps(blueprint.model_dump(), indent=2, default=str),
                encoding="utf-8",
            )
            stages_completed.append("scaffold_project")

            # --- Stage 5: Generate init code (deterministic) ---
            log.info("=== Stage 5: Generating init code ===")
            self._generate_init_code(blueprint, project_dir)
            stages_completed.append("generate_init_code")

            # --- Stage 6: Generate app logic (LLM) ---
            log.info("=== Stage 6: Generating application logic ===")
            vocabulary = self._extract_vocabulary(blueprint)
            code_blocks = self.code_gen.generate(spec, blueprint, vocabulary)
            stages_completed.append("generate_app_logic")

            # --- Stage 6.5: Sanitize code blocks ---
            code_blocks = self._sanitize_code_blocks(code_blocks, blueprint)

            # --- Stage 7: Validate identifiers ---
            log.info("=== Stage 7: Validating identifiers ===")
            validator = IdentifierValidator(vocabulary)
            for block in code_blocks:
                violations = validator.validate(block.get("code", ""))
                if violations:
                    log.warning("Identifier violations in region %s: %s",
                                block.get("region"), [v.identifier for v in violations])
            stages_completed.append("validate_identifiers")

            # --- Stage 8: Inject user code ---
            log.info("=== Stage 8: Injecting user code ===")
            self._inject_user_code(project_dir, code_blocks)
            stages_completed.append("inject_user_code")

            # --- Stage 9: Build ---
            log.info("=== Stage 9: Building project ===")
            result = self.build_agent.build_with_fix_loop(project_dir)
            stages_completed.append("build")

            if result.success:
                # --- Stage 10: Emulation test ---
                log.info("=== Stage 10: Emulation test ===")
                emu_result = self._run_emulation_test(project_dir, blueprint)
                stages_completed.append("emulation_test")

                return PipelineResult(
                    success=True,
                    project_dir=str(project_dir),
                    elf_path=result.elf_path,
                    flash_size=result.flash_size,
                    ram_size=result.ram_size,
                    stages_completed=stages_completed,
                    emulation_result=emu_result,
                )
            else:
                return PipelineResult(
                    success=False,
                    project_dir=str(project_dir),
                    failed_stage="build",
                    error=result.error_message,
                    stages_completed=stages_completed,
                )

        except Exception as e:
            log.exception("Pipeline failed")
            return PipelineResult(
                success=False,
                failed_stage=stages_completed[-1] if stages_completed else "init",
                error=str(e),
                stages_completed=stages_completed,
            )

    def _validate_blueprint(self, blueprint):
        """Run all deterministic validators on the blueprint."""
        # Clock validation
        clock_errors = ClockValidator(self.mcu).validate(blueprint.clock)
        for err in clock_errors:
            if err.severity == "ERROR":
                raise ValueError(f"Clock validation: {err.message}")
            log.warning("Clock: %s", err.message)

        # Pin conflict check
        conflicts = PinConflictValidator().validate(blueprint)
        if conflicts:
            msgs = [f"{c.pin} used by: {', '.join(c.users)}" for c in conflicts]
            raise ValueError(f"Pin conflicts: {'; '.join(msgs)}")

        # Peripheral existence + AF check
        periph_errors = PeripheralValidator(self.mcu).validate(blueprint)
        for err in periph_errors:
            if err.severity == "ERROR":
                raise ValueError(f"Peripheral validation: {err.message}")
            log.warning("Peripheral: %s", err.message)

    def _generate_init_code(self, blueprint, project_dir: Path):
        """Generate all init code deterministically from cookbook recipes."""
        engine = PeripheralEngine(self.mcu)
        codes = engine.generate_all(blueprint)

        # Collect everything
        hal_modules = engine.collect_hal_modules(codes)
        hal_sources = engine.collect_hal_sources(codes)
        handles = engine.collect_handles(codes)
        protos = engine.collect_init_prototypes(codes)
        init_fns = engine.collect_init_functions(codes)
        msp_blocks = engine.collect_msp_inits(codes)
        irq_handlers = engine.collect_irq_handlers(codes)

        # Generate clock config
        clock_engine = ClockEngine(self.mcu)
        clock_code = clock_engine.generate_code(blueprint.clock)

        # Build init call list for main()
        init_calls = []
        if blueprint.gpios:
            init_calls.append("MX_GPIO_Init();")
        for uart in blueprint.uarts:
            init_calls.append(f"MX_{uart.instance}_UART_Init();")
        for spi in blueprint.spis:
            init_calls.append(f"MX_{spi.instance}_Init();")
        for i2c in blueprint.i2cs:
            init_calls.append(f"MX_{i2c.instance}_Init();")
        for tim in blueprint.timers:
            init_calls.append(f"MX_{tim.instance}_Init();")
        for adc in blueprint.adcs:
            init_calls.append(f"MX_{adc.instance}_Init();")

        # Generate main.c
        main_c = generate_main_c(
            includes=[],
            handle_declarations=handles,
            init_prototypes=protos,
            init_calls=init_calls,
            init_functions=init_fns,
            clock_config_fn=clock_code,
        )
        (project_dir / "Core" / "Src" / "main.c").write_text(main_c, encoding="utf-8")

        # Generate main.h
        pin_defines = []
        for gpio in blueprint.gpios:
            if gpio.label:
                port = gpio.pin[1]
                pin_num = int(gpio.pin[2:])
                pin_defines.append((gpio.label, port, pin_num))
        main_h = generate_main_h(pin_defines)
        (project_dir / "Core" / "Inc" / "main.h").write_text(main_h, encoding="utf-8")

        # Generate stm32f4xx_it.c
        it_c = generate_it_c(handles, irq_handlers)
        (project_dir / "Core" / "Src" / "stm32f4xx_it.c").write_text(it_c, encoding="utf-8")

        # Generate stm32f4xx_it.h
        it_h = self._generate_it_h()
        (project_dir / "Core" / "Inc" / "stm32f4xx_it.h").write_text(it_h, encoding="utf-8")

        # Generate hal_msp.c
        # Group MSP blocks by peripheral type
        uart_msps = [c.msp_init for c in codes if c.peripheral_type == "uart" and c.msp_init]
        spi_msps = [c.msp_init for c in codes if c.peripheral_type == "spi" and c.msp_init]
        i2c_msps = [c.msp_init for c in codes if c.peripheral_type == "i2c" and c.msp_init]
        tim_msps = [c.msp_init for c in codes if c.peripheral_type == "timer" and c.msp_init]
        adc_msps = [c.msp_init for c in codes if c.peripheral_type == "adc" and c.msp_init]

        msp_c = generate_hal_msp_c(uart_msps, spi_msps, i2c_msps, tim_msps, adc_msps,
                                   handle_declarations=handles)
        (project_dir / "Core" / "Src" / "stm32f4xx_hal_msp.c").write_text(msp_c, encoding="utf-8")

        # Generate hal_conf.h
        conf_gen = HALConfGenerator()
        hal_conf = conf_gen.generate(hal_modules)
        (project_dir / "Core" / "Inc" / "stm32f4xx_hal_conf.h").write_text(hal_conf, encoding="utf-8")

        # Generate Makefile
        cache = HALCache(self.config.get("hal", {}).get("cache_dir", "~/.stm32_hal_cache"))
        extractor = HALExtractor(cache, blueprint.family)
        all_hal_sources = extractor.get_hal_source_list(
            [t for t in self._get_periph_types(blueprint)]
        )
        makefile = MakefileGenerator().generate(blueprint, all_hal_sources)
        (project_dir / "Makefile").write_text(makefile, encoding="utf-8")

        # Generate linker script
        linker = LinkerGenerator().generate(self.mcu)
        (project_dir / "STM32F446RETx_FLASH.ld").write_text(linker, encoding="utf-8")

        # Ensure startup file
        startup_mgr = StartupManager(cache, blueprint.family)
        startup_mgr.ensure_startup(project_dir, self.mcu_name)

    def _extract_vocabulary(self, blueprint) -> dict:
        """Build the vocabulary for identifier validation."""
        handles = []
        hal_functions = set()
        pin_defines = set()

        for uart in blueprint.uarts:
            h = f"huart{uart.instance[-1]}"
            handles.append(h)
            hal_functions.update([
                "HAL_UART_Init", "HAL_UART_Transmit", "HAL_UART_Receive",
                "HAL_UART_Transmit_IT", "HAL_UART_Receive_IT",
                "HAL_UART_Transmit_DMA", "HAL_UART_Receive_DMA",
                "HAL_UART_IRQHandler", "HAL_UART_TxCpltCallback",
                "HAL_UART_RxCpltCallback",
            ])

        for tim in blueprint.timers:
            h = f"htim{tim.instance.replace('TIM', '').lower()}"
            handles.append(h)
            hal_functions.update([
                "HAL_TIM_Base_Start", "HAL_TIM_Base_Start_IT", "HAL_TIM_Base_Stop",
                "HAL_TIM_PWM_Start", "HAL_TIM_PWM_Stop",
                "HAL_TIM_IC_Start", "HAL_TIM_IC_Start_IT",
                "HAL_TIM_OC_Start", "HAL_TIM_OC_Stop",
                "HAL_TIM_IRQHandler", "HAL_TIM_PeriodElapsedCallback",
                "HAL_TIM_IC_CaptureCallback", "HAL_TIM_PWM_PulseFinishedCallback",
                "__HAL_TIM_GET_COUNTER", "__HAL_TIM_SET_COUNTER",
                "__HAL_TIM_SET_COMPARE", "__HAL_TIM_GET_COMPARE",
            ])

        for spi in blueprint.spis:
            h = f"hspi{spi.instance[-1]}"
            handles.append(h)
            hal_functions.update([
                "HAL_SPI_Init", "HAL_SPI_Transmit", "HAL_SPI_Receive",
                "HAL_SPI_TransmitReceive", "HAL_SPI_Transmit_IT",
                "HAL_SPI_IRQHandler",
            ])

        for i2c in blueprint.i2cs:
            h = f"hi2c{i2c.instance[-1]}"
            handles.append(h)
            hal_functions.update([
                "HAL_I2C_Init", "HAL_I2C_Master_Transmit", "HAL_I2C_Master_Receive",
                "HAL_I2C_Mem_Read", "HAL_I2C_Mem_Write",
                "HAL_I2C_IRQHandler",
            ])

        for adc in blueprint.adcs:
            h = f"hadc{adc.instance[-1]}"
            handles.append(h)
            hal_functions.update([
                "HAL_ADC_Init", "HAL_ADC_Start", "HAL_ADC_Stop",
                "HAL_ADC_Start_IT", "HAL_ADC_Start_DMA",
                "HAL_ADC_PollForConversion", "HAL_ADC_GetValue",
                "HAL_ADC_IRQHandler", "HAL_ADC_ConvCpltCallback",
            ])

        # Common HAL functions
        hal_functions.update([
            "HAL_Init", "HAL_Delay", "HAL_GetTick",
            "HAL_GPIO_WritePin", "HAL_GPIO_ReadPin", "HAL_GPIO_TogglePin",
            "HAL_GPIO_EXTI_Callback",
            "Error_Handler",
        ])

        # Standard C library functions commonly needed
        hal_functions.update([
            "sprintf", "snprintf", "strlen", "memset", "memcpy",
            "strcmp", "strncmp", "printf",
        ])

        # Pin defines
        for gpio in blueprint.gpios:
            if gpio.label:
                pin_defines.add(f"{gpio.label}_Pin")
                pin_defines.add(f"{gpio.label}_GPIO_Port")
            pin_defines.add(f"GPIO_PIN_{int(gpio.pin[2:])}")

        return {
            "handles": handles,
            "hal_functions": sorted(hal_functions),
            "pin_defines": sorted(pin_defines),
            "irq_handlers": [],
            "peripheral_instances": [
                *[u.instance for u in blueprint.uarts],
                *[t.instance for t in blueprint.timers],
                *[s.instance for s in blueprint.spis],
                *[i.instance for i in blueprint.i2cs],
                *[a.instance for a in blueprint.adcs],
            ],
        }

    def _inject_user_code(self, project_dir: Path, code_blocks: list[dict]):
        """Inject LLM-generated code blocks into USER CODE regions."""
        # Group by file
        by_file: dict[str, list[dict]] = {}
        for block in code_blocks:
            fname = block.get("file", "main.c")
            by_file.setdefault(fname, []).append(block)

        for filename, blocks in by_file.items():
            fpath = project_dir / "Core" / "Src" / filename
            if not fpath.is_file():
                log.warning("Target file not found: %s", fpath)
                continue

            content = fpath.read_text(encoding="utf-8")
            for block in blocks:
                region = block.get("region", "")
                code = block.get("code", "")
                if not region or not code:
                    continue

                # Find USER CODE BEGIN <region> ... USER CODE END <region>
                pattern = (
                    rf"(/\* USER CODE BEGIN {re.escape(region)} \*/\n)"
                    rf"(.*?)"
                    rf"(\n\s*/\* USER CODE END {re.escape(region)} \*/)"
                )
                # Escape backslashes in code to prevent regex backreference issues
                safe_code = code.replace("\\", "\\\\")
                replacement = rf"\g<1>{safe_code}\g<3>"
                new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

                if new_content != content:
                    content = new_content
                    log.info("Injected code into %s region %s", filename, region)
                else:
                    log.warning("Region %s not found in %s", region, filename)

            fpath.write_text(content, encoding="utf-8")

    def _sanitize_code_blocks(self, code_blocks: list[dict], blueprint) -> list[dict]:
        """Remove duplicate/conflicting function definitions from LLM output."""
        # Functions that are already defined in the template or init code
        forbidden_fns = {
            "Error_Handler", "assert_failed", "SystemClock_Config",
            "HAL_Init", "main", "MX_GPIO_Init",
        }
        for uart in blueprint.uarts:
            forbidden_fns.add(f"MX_{uart.instance}_UART_Init")
        for spi in blueprint.spis:
            forbidden_fns.add(f"MX_{spi.instance}_Init")
        for i2c in blueprint.i2cs:
            forbidden_fns.add(f"MX_{i2c.instance}_Init")
        for tim in blueprint.timers:
            forbidden_fns.add(f"MX_{tim.instance}_Init")
        for adc in blueprint.adcs:
            forbidden_fns.add(f"MX_{adc.instance}_Init")

        sanitized = []
        for block in code_blocks:
            code = block.get("code", "")
            region = block.get("region", "")

            # Strip any #include lines — already handled
            code = re.sub(r'^\s*#include\s+[<"].*?[>"]\s*$', '', code, flags=re.MULTILINE)

            # Remove re-definitions of forbidden functions
            for fn_name in forbidden_fns:
                # Match: void fn_name(...) { ... } — multi-line function body
                pattern = rf'(?:static\s+)?void\s+{re.escape(fn_name)}\s*\([^)]*\)\s*\{{[^}}]*\}}'
                code = re.sub(pattern, '', code, flags=re.DOTALL)
                # Also remove forward declarations
                pattern = rf'(?:static\s+)?void\s+{re.escape(fn_name)}\s*\([^)]*\)\s*;'
                code = re.sub(pattern, '', code, flags=re.MULTILINE)

            # Strip handle re-declarations (they're already global)
            code = re.sub(r'^\s*(?:extern\s+)?(?:UART|TIM|SPI|I2C|ADC)_HandleTypeDef\s+\w+\s*;',
                          '', code, flags=re.MULTILINE)

            # Clean up excessive blank lines
            code = re.sub(r'\n{3,}', '\n\n', code).strip()

            if code:
                block["code"] = code
                sanitized.append(block)
            else:
                log.info("Sanitized out empty block for region %s", region)

        return sanitized

    def _run_emulation_test(self, project_dir: Path, blueprint) -> dict:
        """Run Stage 10: Renode emulation test."""
        try:
            from emulator.test_runner import test_from_blueprint, find_elf
            elf = find_elf(str(project_dir))
            if not elf:
                log.warning("No .elf found for emulation test")
                return {"status": "SKIP", "detail": "No .elf found"}

            result = test_from_blueprint(elf, blueprint.model_dump())
            log.info("Emulation: %s (%dms)", result.status, result.duration_ms)
            for c in result.checks:
                icon = "+" if c["passed"] else "-"
                log.info("  [%s] %s: %s", icon, c["check"], c["detail"][:80])

            return {
                "status": result.status,
                "duration_ms": result.duration_ms,
                "uart_output": result.uart_output[:500] if result.uart_output else "",
                "checks": result.checks,
            }
        except Exception as e:
            log.warning("Emulation test failed: %s", e)
            return {"status": "ERROR", "detail": str(e)}

    def _generate_it_h(self) -> str:
        """Generate minimal stm32f4xx_it.h."""
        return """\
#ifndef __STM32F4xx_IT_H
#define __STM32F4xx_IT_H

#ifdef __cplusplus
extern "C" {
#endif

void NMI_Handler(void);
void HardFault_Handler(void);
void MemManage_Handler(void);
void BusFault_Handler(void);
void UsageFault_Handler(void);
void SVC_Handler(void);
void DebugMon_Handler(void);
void PendSV_Handler(void);
void SysTick_Handler(void);

#ifdef __cplusplus
}
#endif

#endif /* __STM32F4xx_IT_H */
"""

    def _get_periph_types(self, blueprint) -> list[str]:
        types = set()
        if blueprint.uarts:
            types.add("uart")
        if blueprint.spis:
            types.add("spi")
        if blueprint.i2cs:
            types.add("i2c")
        if blueprint.timers:
            types.add("timer")
        if blueprint.adcs:
            types.add("adc")
        if blueprint.dmas:
            types.add("dma")
        return sorted(types)

    def _load_config(self, path: str) -> dict:
        """Load config from YAML file."""
        config_path = Path(path)
        if config_path.is_file():
            with open(config_path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}
