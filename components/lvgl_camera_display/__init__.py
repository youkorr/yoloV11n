import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID

DEPENDENCIES = ["lvgl"]

CONF_CAMERA_ID = "camera_id"
CONF_ESP32_CAMERA_ID = "esp32_camera_id"
CONF_CANVAS_ID = "canvas_id"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_FACE_DETECTION_ID = "face_detection_id"
CONF_YOLO11_DETECTION_ID = "yolo11_detection_id"
CONF_YOLOV11_ID = "yolov11_id"
CONF_PEDESTRIAN_DETECTION_ID = "pedestrian_detection_id"

lvgl_camera_display_ns = cg.esphome_ns.namespace("lvgl_camera_display")
LVGLCameraDisplay = lvgl_camera_display_ns.class_("LVGLCameraDisplay", cg.Component)

# ESP32-P4 MIPI camera
esp_cam_sensor_ns = cg.esphome_ns.namespace("esp_cam_sensor")
EspCamSensor = esp_cam_sensor_ns.class_("MipiDSICamComponent", cg.Component)

# ESP32-S3 camera
esp32_camera_ns = cg.esphome_ns.namespace("esp32_camera")
ESP32Camera = esp32_camera_ns.class_("ESP32Camera", cg.Component)

# Detection components
face_detection_ns = cg.esphome_ns.namespace("face_detection")
FaceDetectionComponent = face_detection_ns.class_("FaceDetectionComponent", cg.Component)

yolo11_detection_ns = cg.esphome_ns.namespace("yolo11_detection")
YOLO11DetectionComponent = yolo11_detection_ns.class_("YOLO11DetectionComponent", cg.Component)

yolov11_ns = cg.esphome_ns.namespace("yolov11")
YOLOV11Component = yolov11_ns.class_("YOLOV11Component", cg.Component)

pedestrian_detection_ns = cg.esphome_ns.namespace("pedestrian_detection")
PedestrianDetectionComponent = pedestrian_detection_ns.class_("PedestrianDetectionComponent", cg.Component)


def validate_camera_config(config):
    has_mipi = CONF_CAMERA_ID in config
    has_esp32 = CONF_ESP32_CAMERA_ID in config
    if not has_mipi and not has_esp32:
        raise cv.Invalid("Either 'camera_id' or 'esp32_camera_id' must be specified")
    if has_mipi and has_esp32:
        raise cv.Invalid("Only one of 'camera_id' or 'esp32_camera_id' can be specified")
    return config


CONFIG_SCHEMA = cv.All(
    cv.Schema({
        cv.GenerateID(): cv.declare_id(LVGLCameraDisplay),
        cv.Optional(CONF_CAMERA_ID): cv.use_id(EspCamSensor),
        cv.Optional(CONF_ESP32_CAMERA_ID): cv.use_id(ESP32Camera),
        cv.Required(CONF_CANVAS_ID): cv.string,
        cv.Optional(CONF_UPDATE_INTERVAL, default="33ms"): cv.positive_time_period_milliseconds,
        cv.Optional(CONF_FACE_DETECTION_ID): cv.use_id(FaceDetectionComponent),
        cv.Optional(CONF_YOLO11_DETECTION_ID): cv.use_id(YOLO11DetectionComponent),
        cv.Optional(CONF_YOLOV11_ID): cv.use_id(YOLOV11Component),
        cv.Optional(CONF_PEDESTRIAN_DETECTION_ID): cv.use_id(PedestrianDetectionComponent),
    }).extend(cv.COMPONENT_SCHEMA),
    validate_camera_config,
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    # Camera (mutually exclusive)
    if CONF_CAMERA_ID in config:
        camera = await cg.get_variable(config[CONF_CAMERA_ID])
        cg.add(var.set_camera(camera))
        cg.add_build_flag("-DUSE_LVGL_MIPI_CAMERA")
    elif CONF_ESP32_CAMERA_ID in config:
        camera = await cg.get_variable(config[CONF_ESP32_CAMERA_ID])
        cg.add(var.set_esp32_camera(camera))
        cg.add_build_flag("-DUSE_LVGL_ESP32_CAMERA")

    cg.add(var.set_canvas_id(config[CONF_CANVAS_ID]))

    update_interval_ms = config[CONF_UPDATE_INTERVAL].total_milliseconds
    cg.add(var.set_update_interval(int(update_interval_ms)))

    if CONF_FACE_DETECTION_ID in config:
        cg.add_define("USE_FACE_DETECTION")
        face_detect = await cg.get_variable(config[CONF_FACE_DETECTION_ID])
        cg.add(var.set_face_detection(face_detect))

    if CONF_YOLO11_DETECTION_ID in config:
        cg.add_define("USE_YOLO11_DETECTION")
        yolo11_detect = await cg.get_variable(config[CONF_YOLO11_DETECTION_ID])
        cg.add(var.set_yolo11_detection(yolo11_detect))

    if CONF_YOLOV11_ID in config:
        cg.add_define("USE_YOLOV11")
        yolov11 = await cg.get_variable(config[CONF_YOLOV11_ID])
        cg.add(var.set_yolov11(yolov11))

    if CONF_PEDESTRIAN_DETECTION_ID in config:
        cg.add_define("USE_PEDESTRIAN_DETECTION")
        ped_detect = await cg.get_variable(config[CONF_PEDESTRIAN_DETECTION_ID])
        cg.add(var.set_pedestrian_detection(ped_detect))
