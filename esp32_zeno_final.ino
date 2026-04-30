#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <WiFiManager.h>
#include "Audio.h"
#include "driver/i2s_std.h"
// Render manzillaringizni bu yerga yozing
const char* serverUrl = "https://asistent-x0cw.onrender.com/process_audio";
const char* audioUrl = "https://asistent-x0cw.onrender.com/static/response.mp3";
#define BUTTON_PIN 14 
#define I2S_WS 1
#define I2S_SCK 2
#define I2S_SD_IN 3
#define I2S_DOUT 18
#define I2S_BCLK 5
#define I2S_LRC 4
const int sample_rate = 16000;
const int max_samples = sample_rate * 30; 
Audio audio;
i2s_chan_handle_t rx_handle = NULL;
bool is_recording = false;
void setup_mic() {
    i2s_chan_config_t chan_cfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    i2s_new_channel(&chan_cfg, NULL, &rx_handle);
    i2s_std_config_t std_cfg = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(16000),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = {.mclk=I2S_GPIO_UNUSED, .bclk=(gpio_num_t)I2S_SCK, .ws=(gpio_num_t)I2S_WS, .dout=I2S_GPIO_UNUSED, .din=(gpio_num_t)I2S_SD_IN},
    };
    i2s_channel_init_std_mode(rx_handle, &std_cfg);
    i2s_channel_enable(rx_handle);
}
void writeWavHeader(uint8_t* header, int wavSize, int sampleRate, int channels, int bitsPerSample) {
    header[0] = 'R'; header[1] = 'I'; header[2] = 'F'; header[3] = 'F';
    uint32_t fileSize = wavSize + 36;
    header[4] = fileSize & 0xff; header[5] = (fileSize >> 8) & 0xff; header[6] = (fileSize >> 16) & 0xff; header[7] = (fileSize >> 24) & 0xff;
    header[8] = 'W'; header[9] = 'A'; header[10] = 'V'; header[11] = 'E';
    header[12] = 'f'; header[13] = 'm'; header[14] = 't'; header[15] = ' ';
    header[16] = 16; header[17] = 0; header[18] = 0; header[19] = 0;
    header[20] = 1; header[21] = 0; header[22] = channels; header[23] = 0;
    header[24] = sampleRate & 0xff; header[25] = (sampleRate >> 8) & 0xff; header[26] = (sampleRate >> 16) & 0xff; header[27] = (sampleRate >> 24) & 0xff;
    uint32_t byteRate = sampleRate * channels * bitsPerSample / 8;
    header[28] = byteRate & 0xff; header[29] = (byteRate >> 8) & 0xff; header[30] = (byteRate >> 16) & 0xff; header[31] = (byteRate >> 24) & 0xff;
    header[32] = channels * bitsPerSample / 8; header[33] = 0;
    header[34] = bitsPerSample; header[35] = 0;
    header[36] = 'd'; header[37] = 'a'; header[38] = 't'; header[39] = 'a';
    header[40] = wavSize & 0xff; header[41] = (wavSize >> 8) & 0xff; header[42] = (wavSize >> 16) & 0xff; header[43] = (wavSize >> 24) & 0xff;
}
void record_and_send() {
    is_recording = true;
    Serial.println(">>> YOZILMOQDA...");
    int16_t* wav_buffer = (int16_t*)heap_caps_malloc(max_samples * 2 + 44, MALLOC_CAP_SPIRAM);
    int32_t chunk[512]; size_t br; int current_sample = 0;
    while (digitalRead(BUTTON_PIN) == LOW && current_sample < max_samples) {
        i2s_channel_read(rx_handle, chunk, sizeof(chunk), &br, 100);
        for (int i = 0; i < br/8; i++) {
            if (current_sample < max_samples) {
                wav_buffer[22 + current_sample] = (int16_t)(chunk[i*2] >> 12);
                current_sample++;
            }
        }
    }
    writeWavHeader((uint8_t*)wav_buffer, current_sample * 2, sample_rate, 1, 16);
    WiFiClientSecure client; client.setInsecure();
    HTTPClient http; http.begin(client, serverUrl);
    http.setTimeout(60000);
    int hCode = http.POST((uint8_t*)wav_buffer, current_sample * 2 + 44);
    if (hCode == 200) { audio.connecttohost(audioUrl); }
    free(wav_buffer); http.end(); is_recording = false;
}
void setup() {
    Serial.begin(115200); pinMode(BUTTON_PIN, INPUT_PULLUP);
    WiFiManager wm; wm.autoConnect("Zeno Wi-Fi");
    setup_mic(); audio.setPinout(I2S_BCLK, I2S_LRC, I2S_DOUT); audio.setVolume(21);
    Serial.println("Zeno tayyor!");
}
void loop() {
    audio.loop();
    if (digitalRead(BUTTON_PIN) == LOW && !is_recording) {
        delay(50);
        if (digitalRead(BUTTON_PIN) == LOW) {
            if (audio.isRunning()) audio.stopSong();
            record_and_send();
        }
    }
}