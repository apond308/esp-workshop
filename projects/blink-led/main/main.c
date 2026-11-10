// blink-led: blinks the onboard LED of the TENSTAR ESP32-C3 SuperMini Plus at 1 Hz.
// The LED is on GPIO8 and is active-HIGH (verified on this board; see docs/boards/).

#include <inttypes.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_log.h"

#define LED_GPIO      GPIO_NUM_8
#define LED_ON_LEVEL  1            // active-high; set to 0 for boards with an active-low LED
#define LED_OFF_LEVEL (!LED_ON_LEVEL)
#define HALF_PERIOD_MS 500

static const char *TAG = "blink";

void app_main(void)
{
    const gpio_config_t cfg = {
        .pin_bit_mask = 1ULL << LED_GPIO,
        .mode = GPIO_MODE_OUTPUT,
    };
    ESP_ERROR_CHECK(gpio_config(&cfg));
    ESP_LOGI(TAG, "blinking LED on GPIO%d at %d Hz", LED_GPIO, 1000 / (2 * HALF_PERIOD_MS));

    for (uint32_t n = 0;; n++) {
        ESP_ERROR_CHECK(gpio_set_level(LED_GPIO, LED_ON_LEVEL));
        vTaskDelay(pdMS_TO_TICKS(HALF_PERIOD_MS));
        ESP_ERROR_CHECK(gpio_set_level(LED_GPIO, LED_OFF_LEVEL));
        vTaskDelay(pdMS_TO_TICKS(HALF_PERIOD_MS));
        if (n % 5 == 0) {   // log every 5th blink; per-blink logging is noise
            ESP_LOGI(TAG, "alive: blink %" PRIu32, n);
        }
    }
}
