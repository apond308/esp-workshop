// blink-led: find out how the onboard LED is wired on the SuperMini Plus.
// Drives LED_GPIO low for 2 s, then high for 2 s, forever, logging each level.
// A human reports which level lights the LED (-> active-low or active-high).

#include <inttypes.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_log.h"

#define LED_GPIO GPIO_NUM_8   // candidate; also a strapping pin (must stay high at reset)

static const char *TAG = "blink";

void app_main(void)
{
    const gpio_config_t cfg = {
        .pin_bit_mask = 1ULL << LED_GPIO,
        .mode = GPIO_MODE_OUTPUT,
    };
    ESP_ERROR_CHECK(gpio_config(&cfg));
    ESP_LOGI(TAG, "driving GPIO%d: 2 s LOW, 2 s HIGH, repeating", LED_GPIO);

    for (uint32_t n = 0;; n++) {
        ESP_ERROR_CHECK(gpio_set_level(LED_GPIO, 0));
        ESP_LOGI(TAG, "alive: cycle %" PRIu32 " GPIO%d = LOW", n, LED_GPIO);
        vTaskDelay(pdMS_TO_TICKS(2000));
        ESP_ERROR_CHECK(gpio_set_level(LED_GPIO, 1));
        ESP_LOGI(TAG, "alive: cycle %" PRIu32 " GPIO%d = HIGH", n, LED_GPIO);
        vTaskDelay(pdMS_TO_TICKS(2000));
    }
}
