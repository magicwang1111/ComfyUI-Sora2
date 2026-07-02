NODE_PREFIX = "ComfyUI-Sora2"
NODE_CATEGORY = NODE_PREFIX

API_PROVIDER_RELAY = "relay"
API_PROVIDER_OPENAI = "openai"
API_PROVIDER_AZURE = "azure"
API_PROVIDER_OPTIONS = [API_PROVIDER_RELAY, API_PROVIDER_OPENAI, API_PROVIDER_AZURE]
DEFAULT_API_PROVIDER = API_PROVIDER_AZURE

OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_BASE_URL = OPENAI_BASE_URL

MODELS = ["sora-2", "sora-2-pro"]
DEFAULT_MODEL = MODELS[0]

SECONDS_OPTIONS = ["4", "8", "12"]
DEFAULT_SECONDS = "4"

SIZE_OPTIONS = ["720x1280", "1280x720", "1024x1792", "1792x1024"]
IMAGE_TO_VIDEO_SIZE_OPTIONS = ["720x1280", "1280x720"]
DEFAULT_SIZE = SIZE_OPTIONS[0]


def _image_shape(images):
    shape = getattr(images, "shape", None)
    if shape is None:
        raise ValueError("input_image must be a ComfyUI IMAGE tensor.")

    if len(shape) == 3:
        count = 1
        height, width = int(shape[0]), int(shape[1])
    elif len(shape) == 4:
        count = int(shape[0])
        height, width = int(shape[1]), int(shape[2])
    else:
        raise ValueError("input_image must be a 3D or 4D IMAGE tensor.")

    if count != 1:
        raise ValueError("Sora 2 accepts exactly one input reference image.")
    return width, height


def validate_request(model_name, prompt, seconds, size, input_image=None):
    if model_name not in MODELS:
        raise ValueError(f"model must be one of: {', '.join(MODELS)}.")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt is required.")
    if str(seconds) not in SECONDS_OPTIONS:
        raise ValueError(f"seconds must be one of: {', '.join(SECONDS_OPTIONS)}.")
    if size not in SIZE_OPTIONS:
        raise ValueError(f"size must be one of: {', '.join(SIZE_OPTIONS)}.")

    if input_image is not None:
        if size not in IMAGE_TO_VIDEO_SIZE_OPTIONS:
            raise ValueError(
                "Azure Sora 2 image references support size 720x1280 or 1280x720."
            )
        width, height = _image_shape(input_image)
        expected_width, expected_height = (int(part) for part in size.split("x"))
        if (width, height) != (expected_width, expected_height):
            raise ValueError(
                f"input_image is {width}x{height}, but size is {size}. "
                "Resize the image to exactly match the requested video size."
            )
