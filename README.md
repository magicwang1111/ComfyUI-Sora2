# ComfyUI-Sora2

ComfyUI nodes for Azure OpenAI/OpenAI-compatible Sora 2 video generation.

## Nodes

- `ComfyUI-Sora2 Text to Video`
- `ComfyUI-Sora2 Image to Video`

Both nodes return ComfyUI's native `VIDEO` type plus the final task metadata as
JSON. Connect the `VIDEO` output to the built-in Preview Video or Save Video
node.

## Configuration

Copy `config.example.json` to `config.local.json`, then set your endpoint and
API key. `config.local.json` is ignored by Git.

```json
{
  "api_key": "YOUR_API_KEY",
  "api_provider": "azure",
  "base_url": "https://YOUR-RESOURCE-NAME.openai.azure.com/openai/v1",
  "request_timeout": 120,
  "request_retries": 1,
  "retry_delay": 2,
  "poll_interval": 10,
  "generation_timeout": 1800
}
```

Environment variables are also supported:

- `SORA2_API_KEY`, `SORA2_BASE_URL`, `SORA2_API_PROVIDER`
- `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`

Local JSON configuration takes precedence over environment variables. Azure
resource root endpoints are normalized to end in `/openai/v1`.

For Azure, `model_override` should contain the Sora deployment name if it is
different from `sora-2` or `sora-2-pro`.

## Image reference requirements

The image-to-video node accepts exactly one image. The input image dimensions
must exactly match `size`. Azure currently documents reference-image support
for `720x1280` and `1280x720`.

## Install

Install `requirements.txt`, restart ComfyUI, then search for `ComfyUI-Sora2`.
