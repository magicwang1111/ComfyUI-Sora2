import io

import numpy
import PIL.Image
import torch


def _tensor_to_png_bytes(image_tensor):
    if not isinstance(image_tensor, torch.Tensor):
        raise ValueError("input_image must be a torch.Tensor.")

    if image_tensor.ndim == 4:
        image_tensor = image_tensor[0]
    if image_tensor.ndim != 3:
        raise ValueError("input_image must be a 3D or 4D IMAGE tensor.")

    image_array = numpy.clip(
        image_tensor.detach().cpu().numpy() * 255.0, 0.0, 255.0
    ).astype(numpy.uint8)
    image = PIL.Image.fromarray(image_array, mode="RGB")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def build_create_request(model_name, prompt, seconds, size, input_image=None):
    fields = {
        "model": model_name,
        "prompt": prompt.strip(),
        "seconds": str(seconds),
        "size": size,
    }
    files = [(name, (None, value)) for name, value in fields.items()]
    if input_image is not None:
        files.append(
            (
                "input_reference",
                (
                    "input_reference.png",
                    _tensor_to_png_bytes(input_image),
                    "image/png",
                ),
            )
        )
    return None, files
