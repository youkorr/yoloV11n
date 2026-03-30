#include "lvgl_camera_display.h"
#include "esphome/core/log.h"
#include "esphome/core/application.h"
#include <cstring>

#if defined(USE_ESP_IDF) && defined(USE_LVGL_MIPI_CAMERA)
#include "esp_cache.h"
#endif

#ifdef USE_LVGL_ESP32_CAMERA
#include "esphome/components/esp32_camera/esp32_camera.h"
#endif

#ifdef USE_FACE_DETECTION
#include "esphome/components/face_detection/face_detection.h"
#endif
#ifdef USE_YOLO11_DETECTION
#include "esphome/components/yolo11_detection/yolo11_detection.h"
#endif
#ifdef USE_YOLOV11
#include "esphome/components/yolov11/yolov11_component.h"
#endif
#ifdef USE_PEDESTRIAN_DETECTION
#include "esphome/components/pedestrian_detection/pedestrian_detection.h"
#endif

namespace esphome {
namespace lvgl_camera_display {

static const char *const TAG = "lvgl_camera_display";

void LVGLCameraDisplay::setup() {
  ESP_LOGCONFIG(TAG, "Setting up LVGL Camera Display...");

#ifdef USE_LVGL_MIPI_CAMERA
  if (this->mipi_camera_ == nullptr) {
    ESP_LOGE(TAG, "MIPI camera not configured");
    this->mark_failed();
    return;
  }
  if (!this->mipi_camera_->is_pipeline_ready()) {
    ESP_LOGE(TAG, "MIPI camera pipeline not ready");
    this->mark_failed();
    return;
  }
  ESP_LOGI(TAG, "MIPI camera ready");
#endif

#ifdef USE_LVGL_ESP32_CAMERA
  if (this->esp32_camera_ == nullptr) {
    ESP_LOGE(TAG, "ESP32 camera not configured");
    this->mark_failed();
    return;
  }
  // Register callback for ESP32 camera frames
  this->esp32_camera_->add_image_callback(
      [this](std::shared_ptr<esp32_camera::CameraImage> image) {
        this->on_esp32_camera_image_(std::move(image));
      });
  ESP_LOGI(TAG, "ESP32 camera callback registered");
#endif

  ESP_LOGI(TAG, "LVGL Camera Display initialized (update_interval=%ums)", this->update_interval_);
}

void LVGLCameraDisplay::loop() {
  // Start timer when enabled
  if (this->enabled_ && this->lvgl_timer_ == nullptr) {
    ESP_LOGI(TAG, "Starting LVGL Camera Display...");
    this->lvgl_timer_ = lv_timer_create(lvgl_timer_callback_, this->update_interval_, this);
    if (this->lvgl_timer_ != nullptr) {
      ESP_LOGI(TAG, "LVGL Camera Display started");
    }
  }

  // Stop timer when disabled
  if (!this->enabled_ && this->lvgl_timer_ != nullptr) {
    ESP_LOGI(TAG, "Stopping LVGL Camera Display...");
    lv_timer_del(this->lvgl_timer_);
    this->lvgl_timer_ = nullptr;
  }
}

void LVGLCameraDisplay::lvgl_timer_callback_(lv_timer_t *timer) {
  auto *display = static_cast<LVGLCameraDisplay *>(lv_timer_get_user_data(timer));
  if (display != nullptr) {
    display->update_camera_frame_();
  }
}

void LVGLCameraDisplay::update_camera_frame_() {
  uint32_t frame_start = millis();

  // Frame interval tracking
  static uint32_t last_frame_start = 0;
  uint32_t frame_interval = 0;
  if (last_frame_start > 0) {
    frame_interval = frame_start - last_frame_start;
  }
  last_frame_start = frame_start;

#ifdef USE_LVGL_MIPI_CAMERA
  if (this->mipi_camera_ != nullptr && this->mipi_camera_->is_streaming()) {
    static uint32_t attempts = 0;
    static uint32_t skipped = 0;

    bool frame_captured = this->mipi_camera_->capture_frame();
    attempts++;
    if (!frame_captured) {
      skipped++;
      return;
    }
    this->update_canvas_mipi_();
    this->frame_count_++;
  }
#endif

#ifdef USE_LVGL_ESP32_CAMERA
  if (this->esp32_camera_ != nullptr && this->esp32_frame_ready_) {
    this->esp32_frame_ready_ = false;

    if (this->last_esp32_frame_ != nullptr && this->canvas_obj_ != nullptr) {
      uint8_t *img_data = this->last_esp32_frame_;
      uint16_t width = this->last_esp32_width_;
      uint16_t height = this->last_esp32_height_;

      // Draw detection overlays
#ifdef USE_FACE_DETECTION
      if (this->face_detection_ != nullptr) {
        this->face_detection_->draw_on_frame(img_data, width, height);
      }
#endif
#ifdef USE_YOLO11_DETECTION
      if (this->yolo11_detection_ != nullptr) {
        this->yolo11_detection_->draw_on_frame(img_data, width, height);
      }
#endif
#ifdef USE_YOLOV11
      if (this->yolov11_ != nullptr) {
        this->yolov11_->draw_on_frame(img_data, width, height);
      }
#endif
#ifdef USE_PEDESTRIAN_DETECTION
      if (this->pedestrian_detection_ != nullptr) {
        this->pedestrian_detection_->draw_on_frame(img_data, width, height);
      }
#endif

      // Update LVGL display
      uint32_t stride = width * 2;
      uint32_t buf_size = width * height * 2;

      if (!this->draw_buf_initialized_) {
        lv_draw_buf_init(&this->camera_draw_buf_, width, height,
                         LV_COLOR_FORMAT_RGB565, stride, img_data, buf_size);
        lv_draw_buf_set_flag(&this->camera_draw_buf_, LV_IMAGE_FLAGS_MODIFIABLE);
        this->draw_buf_initialized_ = true;
      } else {
        this->camera_draw_buf_.data = img_data;
      }

      if (this->is_canvas_) {
        lv_canvas_set_draw_buf(this->canvas_obj_, &this->camera_draw_buf_);
      } else {
        lv_image_set_src(this->canvas_obj_, &this->camera_draw_buf_);
      }
      lv_obj_invalidate(this->canvas_obj_);

      this->frame_count_++;
    }
  }
#endif

  // Performance stats every 100 frames
  uint32_t frame_end = millis();
  uint32_t frame_cpu_time = frame_end - frame_start;

  static uint32_t last_stats_time = 0;
  static uint32_t total_cpu_time_ms = 0;
  static uint32_t total_frame_interval_ms = 0;
  static uint32_t frame_interval_count = 0;

  total_cpu_time_ms += frame_cpu_time;
  if (frame_interval > 0) {
    total_frame_interval_ms += frame_interval;
    frame_interval_count++;
  }

  if (this->frame_count_ % 100 == 0 && this->frame_count_ > 0) {
    uint32_t now_time = millis();
    if (last_stats_time > 0 && frame_interval_count > 0) {
      float elapsed = (now_time - last_stats_time) / 1000.0f;
      float fps = 100.0f / elapsed;
      float avg_cpu_time = total_cpu_time_ms / 100.0f;
      float avg_frame_interval = total_frame_interval_ms / (float)frame_interval_count;
      float cpu_percent = (avg_cpu_time / avg_frame_interval) * 100.0f;

      this->stats_fps_ = fps;
      this->stats_cpu_percent_ = cpu_percent;
      this->stats_frame_time_ = avg_cpu_time;
      this->stats_lvgl_overhead_ = avg_frame_interval - avg_cpu_time;

      ESP_LOGI(TAG, "FPS: %.1f | CPU: %.1f%% | Frame: %.1fms", fps, cpu_percent, avg_cpu_time);
      this->update_stats_label_();
    }
    last_stats_time = now_time;
    total_cpu_time_ms = 0;
    total_frame_interval_ms = 0;
    frame_interval_count = 0;
  }
}

#ifdef USE_LVGL_ESP32_CAMERA
void LVGLCameraDisplay::on_esp32_camera_image_(
    std::shared_ptr<esp32_camera::CameraImage> image) {
  uint8_t *data = image->get_data_buffer();
  size_t len = image->get_data_length();

  if (data == nullptr || len == 0) return;

  // Determine dimensions from RGB565 frame size
  const uint16_t resolutions[][2] = {
      {320, 240}, {640, 480}, {160, 120}, {800, 600}, {1024, 768},
  };

  for (auto &res : resolutions) {
    if (len == (size_t)res[0] * res[1] * 2) {
      this->last_esp32_frame_ = data;
      this->last_esp32_frame_len_ = len;
      this->last_esp32_width_ = res[0];
      this->last_esp32_height_ = res[1];
      this->esp32_frame_ready_ = true;
      return;
    }
  }
}
#endif

void LVGLCameraDisplay::update_canvas_mipi_() {
#ifdef USE_LVGL_MIPI_CAMERA
  if (this->mipi_camera_ == nullptr || this->canvas_obj_ == nullptr) {
    if (!this->canvas_warning_shown_) {
      ESP_LOGW(TAG, "Canvas/Image null - not configured yet?");
      this->canvas_warning_shown_ = true;
    }
    return;
  }

  // Release previous displayed buffer
  if (this->displayed_buffer_ != nullptr) {
    this->mipi_camera_->release_buffer(this->displayed_buffer_);
    this->displayed_buffer_ = nullptr;
  }

  esp_cam_sensor::SimpleBufferElement *buffer = this->mipi_camera_->acquire_buffer();
  if (buffer == nullptr) return;

  uint8_t *img_data = this->mipi_camera_->get_buffer_data(buffer);
  uint16_t width = this->mipi_camera_->get_image_width();
  uint16_t height = this->mipi_camera_->get_image_height();

  if (img_data == nullptr) return;

  // ESP32-P4: Invalidate CPU cache before reading PSRAM buffer filled by DMA
  uint32_t frame_size = width * height * 2;
  esp_cache_msync(img_data, frame_size,
                  ESP_CACHE_MSYNC_FLAG_DIR_M2C | ESP_CACHE_MSYNC_FLAG_TYPE_DATA);

  // Draw detection overlays on the frame
#ifdef USE_FACE_DETECTION
  if (this->face_detection_ != nullptr) {
    this->face_detection_->draw_on_frame(img_data, width, height);
  }
#endif
#ifdef USE_YOLO11_DETECTION
  if (this->yolo11_detection_ != nullptr) {
    this->yolo11_detection_->draw_on_frame(img_data, width, height);
  }
#endif
#ifdef USE_YOLOV11
  if (this->yolov11_ != nullptr) {
    this->yolov11_->draw_on_frame(img_data, width, height);
  }
#endif
#ifdef USE_PEDESTRIAN_DETECTION
  if (this->pedestrian_detection_ != nullptr) {
    this->pedestrian_detection_->draw_on_frame(img_data, width, height);
  }
#endif

  // ESP32-P4: Flush CPU cache to PSRAM after detection drawing
  esp_cache_msync(img_data, frame_size,
                  ESP_CACHE_MSYNC_FLAG_DIR_C2M | ESP_CACHE_MSYNC_FLAG_TYPE_DATA);

  // Detect widget type on first update
  if (this->first_update_) {
    this->is_canvas_ = lv_obj_check_type(this->canvas_obj_, &lv_canvas_class);
    ESP_LOGI(TAG, "First update - Widget: %s, Size: %ux%u",
             this->is_canvas_ ? "CANVAS" : "IMAGE", width, height);
  }

  // LVGL 9.4 Zero-copy
  uint32_t stride = width * 2;
  uint32_t buf_size = width * height * 2;

  if (!this->draw_buf_initialized_) {
    lv_draw_buf_init(&this->camera_draw_buf_, width, height,
                     LV_COLOR_FORMAT_RGB565, stride, img_data, buf_size);
    lv_draw_buf_set_flag(&this->camera_draw_buf_, LV_IMAGE_FLAGS_MODIFIABLE);
    this->draw_buf_initialized_ = true;
    ESP_LOGI(TAG, "Zero-copy draw_buf: %ux%u, stride=%u", width, height, stride);
  } else {
    this->camera_draw_buf_.data = img_data;
  }

  if (this->is_canvas_) {
    lv_canvas_set_draw_buf(this->canvas_obj_, &this->camera_draw_buf_);
  } else {
    lv_image_set_src(this->canvas_obj_, &this->camera_draw_buf_);
  }

  lv_obj_invalidate(this->canvas_obj_);
  this->first_update_ = false;
  this->displayed_buffer_ = buffer;
#endif
}

void LVGLCameraDisplay::update_stats_label_() {
  if (this->stats_label_ == nullptr) return;
  char buf[64];
  snprintf(buf, sizeof(buf), "FPS: %.1f | CPU: %.1f%%",
           this->stats_fps_, this->stats_cpu_percent_);
  lv_label_set_text(this->stats_label_, buf);
}

void LVGLCameraDisplay::set_stats_label(lv_obj_t *label) {
  this->stats_label_ = label;
  if (label != nullptr) {
    lv_label_set_text(label, "FPS: -- | CPU: --%");
  }
}

void LVGLCameraDisplay::configure_canvas(lv_obj_t *canvas) {
  this->canvas_obj_ = canvas;
  ESP_LOGI(TAG, "Canvas configured: %p", canvas);
  if (canvas != nullptr) {
    lv_coord_t w = lv_obj_get_width(canvas);
    lv_coord_t h = lv_obj_get_height(canvas);
    ESP_LOGI(TAG, "  Size: %dx%d", w, h);
  }
}

void LVGLCameraDisplay::dump_config() {
  ESP_LOGCONFIG(TAG, "LVGL Camera Display:");
#ifdef USE_LVGL_MIPI_CAMERA
  ESP_LOGCONFIG(TAG, "  Camera: MIPI (ESP32-P4)");
#endif
#ifdef USE_LVGL_ESP32_CAMERA
  ESP_LOGCONFIG(TAG, "  Camera: ESP32 Camera (ESP32-S3)");
#endif
  ESP_LOGCONFIG(TAG, "  Update interval: %u ms (~%d FPS)", this->update_interval_,
                1000 / this->update_interval_);
#ifdef USE_YOLOV11
  ESP_LOGCONFIG(TAG, "  YOLOV11: configured");
#endif
#ifdef USE_YOLO11_DETECTION
  ESP_LOGCONFIG(TAG, "  YOLO11 Detection: configured");
#endif
#ifdef USE_FACE_DETECTION
  ESP_LOGCONFIG(TAG, "  Face Detection: configured");
#endif
}

}  // namespace lvgl_camera_display
}  // namespace esphome
