"""STM32F446RE complete hardware profile.

Source: STM32F446xC/E datasheet (DS10693 Rev 9)
  - Table 12: Alternate function mapping (LQFP64 package)
  - Section 2.2: Memory map
  - Section 6: Clock tree
"""

from schemas.mcu_profile import (
    MCUProfile, PinAF, PeripheralInstance, DMAMapping, TimerInfo,
)


def _build_pin_af_table() -> list[dict]:
    """Complete pin-to-AF mapping for STM32F446RE (LQFP64).

    Format: (pin, af_number, peripheral_signal)
    From datasheet Table 12: Alternate function mapping.
    """
    raw = [
        # --- PA0 ---
        ("PA0", 1, "TIM2_CH1"),
        ("PA0", 2, "TIM5_CH1"),
        ("PA0", 3, "TIM8_ETR"),
        ("PA0", 7, "USART2_CTS"),
        ("PA0", 8, "UART4_TX"),
        # --- PA1 ---
        ("PA1", 1, "TIM2_CH2"),
        ("PA1", 2, "TIM5_CH2"),
        ("PA1", 5, "SPI4_MOSI"),
        ("PA1", 7, "USART2_RTS"),
        ("PA1", 8, "UART4_RX"),
        # --- PA2 ---
        ("PA2", 1, "TIM2_CH3"),
        ("PA2", 2, "TIM5_CH3"),
        ("PA2", 3, "TIM9_CH1"),
        ("PA2", 7, "USART2_TX"),
        # --- PA3 ---
        ("PA3", 1, "TIM2_CH4"),
        ("PA3", 2, "TIM5_CH4"),
        ("PA3", 3, "TIM9_CH2"),
        ("PA3", 7, "USART2_RX"),
        # --- PA4 ---
        ("PA4", 5, "SPI1_NSS"),
        ("PA4", 6, "SPI3_NSS"),
        ("PA4", 7, "USART2_CK"),
        ("PA4", 12, "OTG_HS_SOF"),
        # --- PA5 ---
        ("PA5", 1, "TIM2_CH1"),
        ("PA5", 3, "TIM8_CH1N"),
        ("PA5", 5, "SPI1_SCK"),
        # --- PA6 ---
        ("PA6", 1, "TIM1_BKIN"),
        ("PA6", 2, "TIM3_CH1"),
        ("PA6", 3, "TIM8_BKIN"),
        ("PA6", 5, "SPI1_MISO"),
        ("PA6", 9, "TIM13_CH1"),
        # --- PA7 ---
        ("PA7", 1, "TIM1_CH1N"),
        ("PA7", 2, "TIM3_CH2"),
        ("PA7", 3, "TIM8_CH1N"),
        ("PA7", 5, "SPI1_MOSI"),
        ("PA7", 9, "TIM14_CH1"),
        # --- PA8 ---
        ("PA8", 0, "MCO1"),
        ("PA8", 1, "TIM1_CH1"),
        ("PA8", 4, "I2C3_SCL"),
        ("PA8", 7, "USART1_CK"),
        ("PA8", 10, "OTG_FS_SOF"),
        # --- PA9 ---
        ("PA9", 1, "TIM1_CH2"),
        ("PA9", 4, "I2C3_SMBA"),
        ("PA9", 7, "USART1_TX"),
        ("PA9", 10, "OTG_FS_VBUS"),
        # --- PA10 ---
        ("PA10", 1, "TIM1_CH3"),
        ("PA10", 7, "USART1_RX"),
        ("PA10", 10, "OTG_FS_ID"),
        # --- PA11 ---
        ("PA11", 1, "TIM1_CH4"),
        ("PA11", 7, "USART1_CTS"),
        ("PA11", 9, "CAN1_RX"),
        ("PA11", 10, "OTG_FS_DM"),
        # --- PA12 ---
        ("PA12", 1, "TIM1_ETR"),
        ("PA12", 7, "USART1_RTS"),
        ("PA12", 9, "CAN1_TX"),
        ("PA12", 10, "OTG_FS_DP"),
        # --- PA13 (SWDIO) ---
        ("PA13", 0, "JTMS_SWDIO"),
        # --- PA14 (SWCLK) ---
        ("PA14", 0, "JTCK_SWCLK"),
        # --- PA15 ---
        ("PA15", 0, "JTDI"),
        ("PA15", 1, "TIM2_CH1"),
        ("PA15", 5, "SPI1_NSS"),
        ("PA15", 6, "SPI3_NSS"),

        # --- PB0 ---
        ("PB0", 1, "TIM1_CH2N"),
        ("PB0", 2, "TIM3_CH3"),
        ("PB0", 3, "TIM8_CH2N"),
        # --- PB1 ---
        ("PB1", 1, "TIM1_CH3N"),
        ("PB1", 2, "TIM3_CH4"),
        ("PB1", 3, "TIM8_CH3N"),
        # --- PB2 (BOOT1) ---
        # --- PB3 ---
        ("PB3", 0, "JTDO_SWO"),
        ("PB3", 1, "TIM2_CH2"),
        ("PB3", 5, "SPI1_SCK"),
        ("PB3", 6, "SPI3_SCK"),
        ("PB3", 7, "I2S3_CK"),
        # --- PB4 ---
        ("PB4", 0, "NJTRST"),
        ("PB4", 2, "TIM3_CH1"),
        ("PB4", 5, "SPI1_MISO"),
        ("PB4", 6, "SPI3_MISO"),
        ("PB4", 7, "I2S3ext_SD"),
        # --- PB5 ---
        ("PB5", 2, "TIM3_CH2"),
        ("PB5", 4, "I2C1_SMBA"),
        ("PB5", 5, "SPI1_MOSI"),
        ("PB5", 6, "SPI3_MOSI"),
        ("PB5", 9, "CAN2_RX"),
        # --- PB6 ---
        ("PB6", 2, "TIM4_CH1"),
        ("PB6", 4, "I2C1_SCL"),
        ("PB6", 5, "SPI3_MOSI"),  # Note: check datasheet for exact AF
        ("PB6", 7, "USART1_TX"),
        ("PB6", 9, "CAN2_TX"),
        # --- PB7 ---
        ("PB7", 2, "TIM4_CH2"),
        ("PB7", 4, "I2C1_SDA"),
        ("PB7", 7, "USART1_RX"),
        # --- PB8 ---
        ("PB8", 2, "TIM4_CH3"),
        ("PB8", 3, "TIM10_CH1"),
        ("PB8", 4, "I2C1_SCL"),
        ("PB8", 9, "CAN1_RX"),
        # --- PB9 ---
        ("PB9", 2, "TIM4_CH4"),
        ("PB9", 3, "TIM11_CH1"),
        ("PB9", 4, "I2C1_SDA"),
        ("PB9", 5, "SPI2_NSS"),
        ("PB9", 9, "CAN1_TX"),
        # --- PB10 ---
        ("PB10", 1, "TIM2_CH3"),
        ("PB10", 4, "I2C2_SCL"),
        ("PB10", 5, "SPI2_SCK"),
        ("PB10", 7, "USART3_TX"),
        # --- PB12 ---
        ("PB12", 1, "TIM1_BKIN"),
        ("PB12", 4, "I2C2_SMBA"),
        ("PB12", 5, "SPI2_NSS"),
        ("PB12", 7, "USART3_CK"),
        ("PB12", 9, "CAN2_RX"),
        # --- PB13 ---
        ("PB13", 1, "TIM1_CH1N"),
        ("PB13", 5, "SPI2_SCK"),
        ("PB13", 7, "USART3_CTS"),
        ("PB13", 9, "CAN2_TX"),
        # --- PB14 ---
        ("PB14", 1, "TIM1_CH2N"),
        ("PB14", 3, "TIM8_CH2N"),
        ("PB14", 5, "SPI2_MISO"),
        ("PB14", 7, "USART3_RTS"),
        ("PB14", 9, "TIM12_CH1"),
        # --- PB15 ---
        ("PB15", 1, "TIM1_CH3N"),
        ("PB15", 3, "TIM8_CH3N"),
        ("PB15", 5, "SPI2_MOSI"),
        ("PB15", 9, "TIM12_CH2"),

        # --- PC0 ---
        # ADC only (no useful AF for our scope)
        # --- PC1 ---
        ("PC1", 5, "SPI2_MOSI"),  # AF5 on some packages
        # --- PC2 ---
        ("PC2", 5, "SPI2_MISO"),
        # --- PC3 ---
        ("PC3", 5, "SPI2_MOSI"),
        # --- PC4 ---
        # ADC only
        # --- PC5 ---
        # ADC only
        # --- PC6 ---
        ("PC6", 2, "TIM3_CH1"),
        ("PC6", 3, "TIM8_CH1"),
        ("PC6", 5, "I2S2_MCK"),
        ("PC6", 8, "USART6_TX"),
        # --- PC7 ---
        ("PC7", 2, "TIM3_CH2"),
        ("PC7", 3, "TIM8_CH2"),
        ("PC7", 6, "SPI2_SCK"),  # I2S
        ("PC7", 8, "USART6_RX"),
        # --- PC8 ---
        ("PC8", 2, "TIM3_CH3"),
        ("PC8", 3, "TIM8_CH3"),
        # --- PC9 ---
        ("PC9", 0, "MCO2"),
        ("PC9", 2, "TIM3_CH4"),
        ("PC9", 3, "TIM8_CH4"),
        ("PC9", 4, "I2C3_SDA"),
        # --- PC10 ---
        ("PC10", 6, "SPI3_SCK"),
        ("PC10", 7, "USART3_TX"),
        ("PC10", 8, "UART4_TX"),
        # --- PC11 ---
        ("PC11", 6, "SPI3_MISO"),
        ("PC11", 7, "USART3_RX"),
        ("PC11", 8, "UART4_RX"),
        # --- PC12 ---
        ("PC12", 6, "SPI3_MOSI"),
        ("PC12", 7, "USART3_CK"),
        ("PC12", 8, "UART5_TX"),
        # --- PC13 ---
        # GPIO only (user button on NUCLEO)
        # --- PC14 ---
        # OSC32_IN
        # --- PC15 ---
        # OSC32_OUT

        # --- PD2 ---
        ("PD2", 8, "UART5_RX"),

        # --- PH0 ---
        # OSC_IN
        # --- PH1 ---
        # OSC_OUT
    ]
    return [{"pin": p, "af": a, "peripheral": s} for p, a, s in raw]


def _build_peripherals() -> list[dict]:
    """All peripheral instances on STM32F446RE."""
    return [
        # Timers
        {"name": "TIM1",  "type": "timer", "bus": "APB2", "rcc_macro": "__HAL_RCC_TIM1_CLK_ENABLE",  "irq_names": ["TIM1_UP_TIM10_IRQn", "TIM1_CC_IRQn"]},
        {"name": "TIM2",  "type": "timer", "bus": "APB1", "rcc_macro": "__HAL_RCC_TIM2_CLK_ENABLE",  "irq_names": ["TIM2_IRQn"]},
        {"name": "TIM3",  "type": "timer", "bus": "APB1", "rcc_macro": "__HAL_RCC_TIM3_CLK_ENABLE",  "irq_names": ["TIM3_IRQn"]},
        {"name": "TIM4",  "type": "timer", "bus": "APB1", "rcc_macro": "__HAL_RCC_TIM4_CLK_ENABLE",  "irq_names": ["TIM4_IRQn"]},
        {"name": "TIM5",  "type": "timer", "bus": "APB1", "rcc_macro": "__HAL_RCC_TIM5_CLK_ENABLE",  "irq_names": ["TIM5_IRQn"]},
        {"name": "TIM6",  "type": "timer", "bus": "APB1", "rcc_macro": "__HAL_RCC_TIM6_CLK_ENABLE",  "irq_names": ["TIM6_DAC_IRQn"]},
        {"name": "TIM7",  "type": "timer", "bus": "APB1", "rcc_macro": "__HAL_RCC_TIM7_CLK_ENABLE",  "irq_names": ["TIM7_IRQn"]},
        {"name": "TIM8",  "type": "timer", "bus": "APB2", "rcc_macro": "__HAL_RCC_TIM8_CLK_ENABLE",  "irq_names": ["TIM8_UP_TIM13_IRQn", "TIM8_CC_IRQn"]},
        {"name": "TIM9",  "type": "timer", "bus": "APB2", "rcc_macro": "__HAL_RCC_TIM9_CLK_ENABLE",  "irq_names": ["TIM1_BRK_TIM9_IRQn"]},
        {"name": "TIM10", "type": "timer", "bus": "APB2", "rcc_macro": "__HAL_RCC_TIM10_CLK_ENABLE", "irq_names": ["TIM1_UP_TIM10_IRQn"]},
        {"name": "TIM11", "type": "timer", "bus": "APB2", "rcc_macro": "__HAL_RCC_TIM11_CLK_ENABLE", "irq_names": ["TIM1_TRG_COM_TIM11_IRQn"]},
        {"name": "TIM12", "type": "timer", "bus": "APB1", "rcc_macro": "__HAL_RCC_TIM12_CLK_ENABLE", "irq_names": ["TIM8_BRK_TIM12_IRQn"]},
        {"name": "TIM13", "type": "timer", "bus": "APB1", "rcc_macro": "__HAL_RCC_TIM13_CLK_ENABLE", "irq_names": ["TIM8_UP_TIM13_IRQn"]},
        {"name": "TIM14", "type": "timer", "bus": "APB1", "rcc_macro": "__HAL_RCC_TIM14_CLK_ENABLE", "irq_names": ["TIM8_TRG_COM_TIM14_IRQn"]},

        # UARTs
        {"name": "USART1", "type": "uart", "bus": "APB2", "rcc_macro": "__HAL_RCC_USART1_CLK_ENABLE", "irq_names": ["USART1_IRQn"]},
        {"name": "USART2", "type": "uart", "bus": "APB1", "rcc_macro": "__HAL_RCC_USART2_CLK_ENABLE", "irq_names": ["USART2_IRQn"]},
        {"name": "USART3", "type": "uart", "bus": "APB1", "rcc_macro": "__HAL_RCC_USART3_CLK_ENABLE", "irq_names": ["USART3_IRQn"]},
        {"name": "UART4",  "type": "uart", "bus": "APB1", "rcc_macro": "__HAL_RCC_UART4_CLK_ENABLE",  "irq_names": ["UART4_IRQn"]},
        {"name": "UART5",  "type": "uart", "bus": "APB1", "rcc_macro": "__HAL_RCC_UART5_CLK_ENABLE",  "irq_names": ["UART5_IRQn"]},
        {"name": "USART6", "type": "uart", "bus": "APB2", "rcc_macro": "__HAL_RCC_USART6_CLK_ENABLE", "irq_names": ["USART6_IRQn"]},

        # SPI
        {"name": "SPI1", "type": "spi", "bus": "APB2", "rcc_macro": "__HAL_RCC_SPI1_CLK_ENABLE", "irq_names": ["SPI1_IRQn"]},
        {"name": "SPI2", "type": "spi", "bus": "APB1", "rcc_macro": "__HAL_RCC_SPI2_CLK_ENABLE", "irq_names": ["SPI2_IRQn"]},
        {"name": "SPI3", "type": "spi", "bus": "APB1", "rcc_macro": "__HAL_RCC_SPI3_CLK_ENABLE", "irq_names": ["SPI3_IRQn"]},
        {"name": "SPI4", "type": "spi", "bus": "APB2", "rcc_macro": "__HAL_RCC_SPI4_CLK_ENABLE", "irq_names": ["SPI4_IRQn"]},

        # I2C
        {"name": "I2C1", "type": "i2c", "bus": "APB1", "rcc_macro": "__HAL_RCC_I2C1_CLK_ENABLE", "irq_names": ["I2C1_EV_IRQn", "I2C1_ER_IRQn"]},
        {"name": "I2C2", "type": "i2c", "bus": "APB1", "rcc_macro": "__HAL_RCC_I2C2_CLK_ENABLE", "irq_names": ["I2C2_EV_IRQn", "I2C2_ER_IRQn"]},
        {"name": "I2C3", "type": "i2c", "bus": "APB1", "rcc_macro": "__HAL_RCC_I2C3_CLK_ENABLE", "irq_names": ["I2C3_EV_IRQn", "I2C3_ER_IRQn"]},

        # ADC
        {"name": "ADC1", "type": "adc", "bus": "APB2", "rcc_macro": "__HAL_RCC_ADC1_CLK_ENABLE", "irq_names": ["ADC_IRQn"]},
        {"name": "ADC2", "type": "adc", "bus": "APB2", "rcc_macro": "__HAL_RCC_ADC2_CLK_ENABLE", "irq_names": ["ADC_IRQn"]},
        {"name": "ADC3", "type": "adc", "bus": "APB2", "rcc_macro": "__HAL_RCC_ADC3_CLK_ENABLE", "irq_names": ["ADC_IRQn"]},

        # DAC
        {"name": "DAC", "type": "dac", "bus": "APB1", "rcc_macro": "__HAL_RCC_DAC_CLK_ENABLE", "irq_names": ["TIM6_DAC_IRQn"]},

        # DMA
        {"name": "DMA1", "type": "dma", "bus": "AHB1", "rcc_macro": "__HAL_RCC_DMA1_CLK_ENABLE", "irq_names": []},
        {"name": "DMA2", "type": "dma", "bus": "AHB1", "rcc_macro": "__HAL_RCC_DMA2_CLK_ENABLE", "irq_names": []},

        # CAN
        {"name": "CAN1", "type": "can", "bus": "APB1", "rcc_macro": "__HAL_RCC_CAN1_CLK_ENABLE", "irq_names": ["CAN1_TX_IRQn", "CAN1_RX0_IRQn"]},
        {"name": "CAN2", "type": "can", "bus": "APB1", "rcc_macro": "__HAL_RCC_CAN2_CLK_ENABLE", "irq_names": ["CAN2_TX_IRQn", "CAN2_RX0_IRQn"]},
    ]


def _build_dma_mappings() -> list[dict]:
    """DMA request mappings from reference manual Table 28/29."""
    return [
        # DMA1
        {"peripheral": "SPI3_RX",   "dma": 1, "stream": 0, "channel": 0},
        {"peripheral": "I2C1_RX",   "dma": 1, "stream": 0, "channel": 1},
        {"peripheral": "TIM4_CH1",  "dma": 1, "stream": 0, "channel": 2},
        {"peripheral": "UART5_RX",  "dma": 1, "stream": 0, "channel": 4},
        {"peripheral": "SPI3_RX",   "dma": 1, "stream": 2, "channel": 0},
        {"peripheral": "TIM4_CH2",  "dma": 1, "stream": 3, "channel": 2},
        {"peripheral": "USART3_TX", "dma": 1, "stream": 3, "channel": 4},
        {"peripheral": "SPI2_TX",   "dma": 1, "stream": 4, "channel": 0},
        {"peripheral": "I2C3_TX",   "dma": 1, "stream": 4, "channel": 3},
        {"peripheral": "UART4_TX",  "dma": 1, "stream": 4, "channel": 4},
        {"peripheral": "USART2_RX", "dma": 1, "stream": 5, "channel": 4},
        {"peripheral": "USART2_TX", "dma": 1, "stream": 6, "channel": 4},
        {"peripheral": "I2C1_TX",   "dma": 1, "stream": 6, "channel": 1},
        {"peripheral": "TIM4_UP",   "dma": 1, "stream": 6, "channel": 2},
        {"peripheral": "SPI3_TX",   "dma": 1, "stream": 7, "channel": 0},
        {"peripheral": "I2C1_TX",   "dma": 1, "stream": 7, "channel": 1},
        {"peripheral": "UART5_TX",  "dma": 1, "stream": 7, "channel": 4},

        # DMA2
        {"peripheral": "ADC1",       "dma": 2, "stream": 0, "channel": 0},
        {"peripheral": "TIM8_CH1",   "dma": 2, "stream": 2, "channel": 7},
        {"peripheral": "SPI1_RX",    "dma": 2, "stream": 0, "channel": 3},
        {"peripheral": "SPI1_RX",    "dma": 2, "stream": 2, "channel": 3},
        {"peripheral": "SPI1_TX",    "dma": 2, "stream": 3, "channel": 3},
        {"peripheral": "SPI1_TX",    "dma": 2, "stream": 5, "channel": 3},
        {"peripheral": "USART1_RX",  "dma": 2, "stream": 2, "channel": 4},
        {"peripheral": "USART1_RX",  "dma": 2, "stream": 5, "channel": 4},
        {"peripheral": "USART1_TX",  "dma": 2, "stream": 7, "channel": 4},
        {"peripheral": "USART6_RX",  "dma": 2, "stream": 1, "channel": 5},
        {"peripheral": "USART6_TX",  "dma": 2, "stream": 6, "channel": 5},
        {"peripheral": "ADC2",       "dma": 2, "stream": 2, "channel": 1},
        {"peripheral": "ADC3",       "dma": 2, "stream": 0, "channel": 2},
        {"peripheral": "TIM1_CH1",   "dma": 2, "stream": 1, "channel": 6},
        {"peripheral": "TIM1_CH2",   "dma": 2, "stream": 2, "channel": 6},
        {"peripheral": "TIM1_CH3",   "dma": 2, "stream": 6, "channel": 6},
        {"peripheral": "SPI4_RX",    "dma": 2, "stream": 0, "channel": 4},
        {"peripheral": "SPI4_TX",    "dma": 2, "stream": 1, "channel": 4},
    ]


def _build_timers() -> list[dict]:
    """Timer metadata."""
    return [
        {"name": "TIM1",  "is_advanced": True,  "is_32bit": False, "channels": 4, "bus": "APB2"},
        {"name": "TIM2",  "is_advanced": False, "is_32bit": True,  "channels": 4, "bus": "APB1"},
        {"name": "TIM3",  "is_advanced": False, "is_32bit": False, "channels": 4, "bus": "APB1"},
        {"name": "TIM4",  "is_advanced": False, "is_32bit": False, "channels": 4, "bus": "APB1"},
        {"name": "TIM5",  "is_advanced": False, "is_32bit": True,  "channels": 4, "bus": "APB1"},
        {"name": "TIM6",  "is_advanced": False, "is_32bit": False, "channels": 0, "bus": "APB1"},
        {"name": "TIM7",  "is_advanced": False, "is_32bit": False, "channels": 0, "bus": "APB1"},
        {"name": "TIM8",  "is_advanced": True,  "is_32bit": False, "channels": 4, "bus": "APB2"},
        {"name": "TIM9",  "is_advanced": False, "is_32bit": False, "channels": 2, "bus": "APB2"},
        {"name": "TIM10", "is_advanced": False, "is_32bit": False, "channels": 1, "bus": "APB2"},
        {"name": "TIM11", "is_advanced": False, "is_32bit": False, "channels": 1, "bus": "APB2"},
        {"name": "TIM12", "is_advanced": False, "is_32bit": False, "channels": 2, "bus": "APB1"},
        {"name": "TIM13", "is_advanced": False, "is_32bit": False, "channels": 1, "bus": "APB1"},
        {"name": "TIM14", "is_advanced": False, "is_32bit": False, "channels": 1, "bus": "APB1"},
    ]


# ADC channel-to-pin mapping for STM32F446RE
ADC_CHANNEL_PINS: dict[int, str] = {
    0: "PA0",
    1: "PA1",
    2: "PA2",
    3: "PA3",
    4: "PA4",
    5: "PA5",
    6: "PA6",
    7: "PA7",
    8: "PB0",
    9: "PB1",
    10: "PC0",
    11: "PC1",
    12: "PC2",
    13: "PC3",
    14: "PC4",
    15: "PC5",
    # 16 = internal temp sensor
    # 17 = internal VREFINT
    # 18 = VBAT
}

# GPIO port clock enable macros
GPIO_PORT_RCC: dict[str, str] = {
    "A": "__HAL_RCC_GPIOA_CLK_ENABLE",
    "B": "__HAL_RCC_GPIOB_CLK_ENABLE",
    "C": "__HAL_RCC_GPIOC_CLK_ENABLE",
    "D": "__HAL_RCC_GPIOD_CLK_ENABLE",
    "E": "__HAL_RCC_GPIOE_CLK_ENABLE",
    "H": "__HAL_RCC_GPIOH_CLK_ENABLE",
}


def get_stm32f446re_profile() -> MCUProfile:
    """Return the complete STM32F446RE hardware profile."""
    return MCUProfile(
        name="STM32F446RETx",
        family="stm32f4",
        core="cortex-m4",
        fpu=True,
        flash_size_kb=512,
        sram_size_kb=128,
        flash_base=0x08000000,
        sram_base=0x20000000,
        max_sysclk_mhz=180,
        max_apb1_mhz=45,
        max_apb2_mhz=90,
        hse_default_mhz=8,
        gpio_ports=["A", "B", "C", "D", "E", "H"],
        pin_af_table=[PinAF(**e) for e in _build_pin_af_table()],
        peripherals=[PeripheralInstance(**e) for e in _build_peripherals()],
        dma_mappings=[DMAMapping(**e) for e in _build_dma_mappings()],
        timers=[TimerInfo(**e) for e in _build_timers()],
    )
