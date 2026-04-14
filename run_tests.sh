#!/bin/bash
# Sequential test runner for V6 STM32 Agent - Prompts 1-7
export PATH="/c/ST/STM32CubeIDE_2.1.0/STM32CubeIDE/plugins/com.st.stm32cube.ide.mcu.externaltools.make.win32_2.2.100.202601091506/tools/bin:$PATH"

cd "C:/Users/hacke/Documents/STM32_Agentic_V6"

PROMPTS=(
  "Blink an LED on PA5 at 1Hz"
  "Send Hello World over UART at 115200 baud"
  "Read a push button on PC13 and turn on LED on PA5 when pressed"
  "Generate a 1kHz PWM signal on PA0 using TIM2 to dim an LED"
  "Read an analog voltage on PA0 using ADC1 and print the value over UART2 at 115200 baud"
  "Configure SPI1 as master at 1MHz clock mode 0 on PA5 PA6 PA7 with CS on PA4"
  "Set up I2C1 at 100kHz on PB8 PB9 to communicate with a sensor"
)

DIRS=(
  "test1_led_blink"
  "test2_uart_hello"
  "test3_button_led"
  "test4_pwm_led"
  "test5_adc_uart"
  "test6_spi_master"
  "test7_i2c_sensor"
)

for i in {0..6}; do
  N=$((i+1))
  echo ""
  echo "================================================================"
  echo "  TEST $N: ${PROMPTS[$i]}"
  echo "================================================================"
  echo ""

  rm -rf "generated/${DIRS[$i]}"

  START=$(date +%s)
  python run.py "${PROMPTS[$i]}" --output "./generated/${DIRS[$i]}" -v 2>&1 | tee "/tmp/test${N}.log"
  END=$(date +%s)
  ELAPSED=$((END - START))

  echo ""
  echo ">>> TEST $N completed in ${ELAPSED}s"
  echo ""
done

echo ""
echo "================================================================"
echo "  ALL TESTS COMPLETE - SUMMARY"
echo "================================================================"
for i in {0..6}; do
  N=$((i+1))
  if grep -q "Build SUCCESS" "/tmp/test${N}.log" 2>/dev/null; then
    FLASH=$(grep "Flash:" "/tmp/test${N}.log" | tail -1)
    echo "  TEST $N: PASS  $FLASH"
  else
    STAGE=$(grep "Build FAILED" "/tmp/test${N}.log" | tail -1)
    echo "  TEST $N: FAIL  $STAGE"
  fi
done
