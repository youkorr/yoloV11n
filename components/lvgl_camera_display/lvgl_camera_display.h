#pragma once

#include "esphome/core/component.h"
#include "esphome/components/lvgl/lvgl_esphome.h"

#ifdef USE_LVGL_MIPI_CAMERA
#include "esphome/components/esp_cam_sensor/esp_cam_sensor_camera.h"
#endif

#ifdef USE_LVGL_ESP32_CAMERA
namespace esp32_camera {
class ESP32Camera;
class CameraImage;
}  // namespace esp32_camera
#endif

// Forward declarations for optional detection components
namespace esphome {
namespace face_detection {
class FaceDetectionComponent;
}
namespace yolo11_detection {
class YOLO11DetectionComponent;
}
namespace yolov11 {
class YOLOV11Component;
}
namespace pedestrian_detection {
class PedestrianDetectionComponent;
}
}  // namespace esphome

namespace esphome {
namespace lvgl_camera_display {

class LVGLCameraDisplay : public Component {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;

#ifdef USE_LVGL_MIPI_CAMERA
  void set_camera(esp_cam_sensor::MipiDSICamComponent *camera) { this->mipi_camera_ = camera; }
#endif
#ifdef USE_LVGL_ESP32_CAMERA
  void set_esp32_camera(esp32_camera::ESP32Camera *camera) { this->esp32_camera_ = camera; }
#endif

  void set_canvas_id(const std::string &canvas_id) { this->canvas_id_ = canvas_id; }
  void set_update_interval(uint32_t interval_ms) { this->update_interval_ = interval_ms; }
  void set_enabled(bool enabled) { this->enabled_ = enabled; }

#ifdef USE_FACE_DETECTION
  void set_face_detection(face_detection::FaceDetectionComponent *fd) { this->face_detection_ = fd; }
#endif
#ifdef USE_YOLO11_DETECTION
  void set_yolo11_detection(yolo11_detection::YOLO11DetectionComponent *yd) { this->yolo11_detection_ = yd; }
#endif
#ifdef USE_YOLOV11
  void set_yolov11(yolov11::YOLOV11Component *yv) { this->yolov11_ = yv; }
#endif
#ifdef USE_PEDESTRIAN_DETECTION
  void set_pedestrian_detection(pedestrian_detection::PedestrianDetectionComponent *pd) { this->pedestrian_detection_ = pd; }
#endif

  void configure_canvas(lv_obj_t *canvas);
  void set_stats_label(lv_obj_t *label);

  float get_fps() const { return this->stats_fps_; }
  float get_cpu_percent() const { return this->stats_cpu_percent_; }
  float get_frame_time() const { return this->stats_frame_time_; }

  float get_setup_priority() const override { return setup_priority::LATE; }

  static void lvgl_timer_callback_(lv_timer_t *timer);

 protected:
#ifdef USE_LVGL_MIPI_CAMERA
  esp_cam_sensor::MipiDSICamComponent *mipi_camera_{nullptr};
#endif
#ifdef USE_LVGL_ESP32_CAMERA
  esp32_camera::ESP32Camera *esp32_camera_{nullptr};
#endif

#ifdef USE_FACE_DETECTION
  face_detection::FaceDetectionComponent *face_detection_{nullptr};
#endif
#ifdef USE_YOLO11_DETECTION
  yolo11_detection::YOLO11DetectionComponent *yolo11_detection_{nullptr};
#endif
#ifdef USE_YOLOV11
  yolov11::YOLOV11Component *yolov11_{nullptr};
#endif
#ifdef USE_PEDESTRIAN_DETECTION
  pedestrian_detection::PedestrianDetectionComponent *pedestrian_detection_{nullptr};
#endif

  lv_obj_t *canvas_obj_{nullptr};
  std::string canvas_id_{};

  uint32_t update_interval_{33};
  uint32_t last_update_{0};
  uint32_t frame_count_{0};
  bool first_update_{true};
  bool canvas_warning_shown_{false};
  bool enabled_{false};

  lv_timer_t *lvgl_timer_{nullptr};

#ifdef USE_LVGL_MIPI_CAMERA
  esp_cam_sensor::SimpleBufferElement *displayed_buffer_{nullptr};
#endif

  // LVGL 9.4 Zero-copy draw buffer
  lv_draw_buf_t camera_draw_buf_{};
  bool draw_buf_initialized_{false};
  bool is_canvas_{false};

  // Stats
  lv_obj_t *stats_label_{nullptr};
  float stats_fps_{0.0f};
  float stats_cpu_percent_{0.0f};
  float stats_frame_time_{0.0f};
  float stats_lvgl_overhead_{0.0f};

  void update_camera_frame_();
  void update_canvas_mipi_();
  void update_stats_label_();

#ifdef USE_LVGL_ESP32_CAMERA
  void on_esp32_camera_image_(std::shared_ptr<esp32_camera::CameraImage> image);
  uint8_t *last_esp32_frame_{nullptr};
  size_t last_esp32_frame_len_{0};
  uint16_t last_esp32_width_{0};
  uint16_t last_esp32_height_{0};
  bool esp32_frame_ready_{false};
#endif
};

}  // namespace lvgl_camera_display
}  // namespace esphome
