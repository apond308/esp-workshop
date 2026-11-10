// hello-c3: starting point generated from templates/esp32c3-idf.
// Prints build/chip info at boot, then a heartbeat line every 5 s.
// The heartbeat ("alive:") is what `esp.py flash --until alive:` waits for.

#include <inttypes.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_app_desc.h"
#include "esp_chip_info.h"
#include "esp_flash.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_timer.h"

static const char *TAG = "main";

void app_main(void)
{
    const esp_app_desc_t *app = esp_app_get_description();
    esp_chip_info_t chip;
    esp_chip_info(&chip);
    uint32_t flash_bytes = 0;
    ESP_ERROR_CHECK(esp_flash_get_size(NULL, &flash_bytes));

    ESP_LOGI(TAG, "%s %s (IDF %s), built %s %s",
             app->project_name, app->version, app->idf_ver, app->date, app->time);
    ESP_LOGI(TAG, "chip rev v%d.%d, %d core(s), %" PRIu32 " MB flash, reset reason %d",
             chip.revision / 100, chip.revision % 100, chip.cores,
             flash_bytes / (1024 * 1024), (int)esp_reset_reason());

    while (true) {
        ESP_LOGI(TAG, "alive: uptime %" PRId64 " s, free heap %" PRIu32 " B, min free %" PRIu32 " B",
                 esp_timer_get_time() / 1000000, esp_get_free_heap_size(),
                 esp_get_minimum_free_heap_size());
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}
