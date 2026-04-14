"""Clock tree solver and SystemClock_Config() code generator.

Replaces CubeMX's clock configurator for STM32F4.
PLL formula: SYSCLK = (HSE / PLL_M) * PLL_N / PLL_P
Constraints:
  - 1 MHz <= HSE/PLL_M <= 2 MHz (VCO input)
  - 100 MHz <= (HSE/PLL_M)*PLL_N <= 432 MHz (VCO output)
  - PLL_P in {2, 4, 6, 8}
  - SYSCLK <= max_sysclk_mhz
"""

from __future__ import annotations
import logging

from schemas.peripheral_config import ClockConfig
from schemas.mcu_profile import MCUProfile

log = logging.getLogger(__name__)

# Valid PLL_P divider values
VALID_PLL_P = [2, 4, 6, 8]


class ClockEngine:
    """Solves PLL parameters and generates SystemClock_Config() C code."""

    def __init__(self, mcu: MCUProfile):
        self.mcu = mcu

    def solve(self, target_sysclk_mhz: int, hse_mhz: int | None = None) -> ClockConfig:
        """Find PLL_M, PLL_N, PLL_P to produce the target SYSCLK.

        Tries all valid combinations and picks the one with exact match
        or closest achievable frequency.
        """
        hse = hse_mhz or self.mcu.hse_default_mhz
        target = min(target_sysclk_mhz, self.mcu.max_sysclk_mhz)

        best: ClockConfig | None = None
        best_error = float("inf")

        for pll_m in range(hse, hse * 2 + 1):  # VCO_input = 1 or 2 MHz
            vco_input = hse / pll_m
            if not (1.0 <= vco_input <= 2.0):
                continue

            for pll_p in VALID_PLL_P:
                # SYSCLK = (HSE / PLL_M) * PLL_N / PLL_P
                # PLL_N = SYSCLK * PLL_P * PLL_M / HSE
                pll_n_f = target * pll_p * pll_m / hse
                pll_n = round(pll_n_f)

                if not (50 <= pll_n <= 432):
                    continue

                vco_output = (hse / pll_m) * pll_n
                if not (100.0 <= vco_output <= 432.0):
                    continue

                actual_sysclk = vco_output / pll_p
                error = abs(actual_sysclk - target)

                if error < best_error:
                    best_error = error
                    # Calculate bus prescalers
                    apb1_pre, apb2_pre = self._solve_bus_prescalers(int(actual_sysclk))
                    sysclk = int(actual_sysclk)
                    hclk = sysclk  # AHB prescaler = 1
                    apb1 = hclk // apb1_pre
                    apb2 = hclk // apb2_pre
                    # Timer clocks: if APBx prescaler > 1, timer clock = 2 * APBx
                    apb1_tim = apb1 * 2 if apb1_pre > 1 else apb1
                    apb2_tim = apb2 * 2 if apb2_pre > 1 else apb2

                    best = ClockConfig(
                        hse_mhz=hse,
                        pll_m=pll_m,
                        pll_n=pll_n,
                        pll_p=pll_p,
                        pll_q=max(2, round(vco_output / 48)),  # USB needs 48MHz
                        ahb_prescaler=1,
                        apb1_prescaler=apb1_pre,
                        apb2_prescaler=apb2_pre,
                        sysclk_mhz=sysclk,
                        hclk_mhz=hclk,
                        apb1_mhz=apb1,
                        apb2_mhz=apb2,
                        apb1_timer_mhz=apb1_tim,
                        apb2_timer_mhz=apb2_tim,
                    )

                    if error == 0:
                        return best

        if best is None:
            raise ValueError(
                f"Cannot solve PLL for {target_sysclk_mhz}MHz SYSCLK with {hse}MHz HSE"
            )

        if best_error > 0:
            log.warning(
                "Exact SYSCLK=%dMHz not achievable; using %dMHz (error=%.1fMHz)",
                target_sysclk_mhz, best.sysclk_mhz, best_error,
            )
        return best

    def _solve_bus_prescalers(self, sysclk_mhz: int) -> tuple[int, int]:
        """Find APB1 and APB2 prescalers to stay within limits."""
        max_apb1 = self.mcu.max_apb1_mhz
        max_apb2 = self.mcu.max_apb2_mhz

        # APB1 prescaler
        for pre in [1, 2, 4, 8, 16]:
            if sysclk_mhz // pre <= max_apb1:
                apb1_pre = pre
                break
        else:
            apb1_pre = 16

        # APB2 prescaler
        for pre in [1, 2, 4, 8, 16]:
            if sysclk_mhz // pre <= max_apb2:
                apb2_pre = pre
                break
        else:
            apb2_pre = 16

        return apb1_pre, apb2_pre

    def generate_code(self, config: ClockConfig) -> str:
        """Generate the SystemClock_Config() function body as C code."""
        # Map prescaler value → HAL macro
        ahb_map = {1: "RCC_SYSCLK_DIV1", 2: "RCC_SYSCLK_DIV2", 4: "RCC_SYSCLK_DIV4",
                    8: "RCC_SYSCLK_DIV8", 16: "RCC_SYSCLK_DIV16"}
        apb_map = {1: "RCC_HCLK_DIV1", 2: "RCC_HCLK_DIV2", 4: "RCC_HCLK_DIV4",
                   8: "RCC_HCLK_DIV8", 16: "RCC_HCLK_DIV16"}

        # Flash latency based on SYSCLK (2.7V-3.6V range)
        if config.sysclk_mhz <= 30:
            latency = 0
        elif config.sysclk_mhz <= 60:
            latency = 1
        elif config.sysclk_mhz <= 90:
            latency = 2
        elif config.sysclk_mhz <= 120:
            latency = 3
        elif config.sysclk_mhz <= 150:
            latency = 4
        else:
            latency = 5

        # Determine PLL_P register value (2→0, 4→1, 6→2, 8→3)
        pll_p_reg = (config.pll_p // 2) - 1
        pll_p_macro = f"RCC_PLLP_DIV{config.pll_p}"

        return f"""\
void SystemClock_Config(void)
{{
  RCC_OscInitTypeDef RCC_OscInitStruct = {{0}};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {{0}};

  /** Configure the main internal regulator output voltage */
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

  /** Initializes the RCC Oscillators according to the specified parameters */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = {config.pll_m}U;
  RCC_OscInitStruct.PLL.PLLN = {config.pll_n}U;
  RCC_OscInitStruct.PLL.PLLP = {pll_p_macro};
  RCC_OscInitStruct.PLL.PLLQ = {config.pll_q}U;
  RCC_OscInitStruct.PLL.PLLR = 2U;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {{
    Error_Handler();
  }}

  /** Activate the Over-Drive mode (required for 180MHz on F446) */
  if (HAL_PWREx_EnableOverDrive() != HAL_OK)
  {{
    Error_Handler();
  }}

  /** Initializes the CPU, AHB and APB bus clocks */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK
                               | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = {ahb_map[config.ahb_prescaler]};
  RCC_ClkInitStruct.APB1CLKDivider = {apb_map[config.apb1_prescaler]};
  RCC_ClkInitStruct.APB2CLKDivider = {apb_map[config.apb2_prescaler]};

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_{latency}) != HAL_OK)
  {{
    Error_Handler();
  }}
}}"""
