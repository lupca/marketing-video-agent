# Slideshow Worker — Agent & API Integration

This document outlines the JSON schema expected by the `worker_slideshow` when pushing a new job via the `/api/jobs` endpoint.

To create a Slideshow job, use the `slideshow` job type. The API requires the `config_data` field to strictly follow this structure:

## Example JSON Payload

```json
{
  "job_type": "slideshow",
  "project_id": "uuid-here",
  "priority": 0,
  "asset_ids": [
    "uuid-for-image1",
    "uuid-for-image2",
    "uuid-for-bg-music"
  ],
  "config_data": {
    "variant": "A",
    "assets": {
      "bg_music": "s3://videos/assets/audio/my_track.mp3",
      "logo": "s3://videos/assets/image/my_logo.png"
    },
    "input_json": {
      "intro_text": "Top 5 sản phẩm nổi bật\nGiảm sâu hôm nay!",
      "outro_text": "Click giỏ hàng phía dưới\nĐể mua ngay!",
      "products": [
        {
          "image": "s3://videos/assets/image/product1.jpeg",
          "text": "Bàn Phím Cơ RK61",
          "hook": "Hot Trend"
        },
        {
          "image": "s3://videos/assets/image/product2.jpeg",
          "text": "Chuột Không Dây Logitech",
          "hook": "Giảm 50%"
        }
      ]
    }
  }
}
```

## Schema Breakdown

### `config_data.variant`
A string literal determining the style of the slideshow. 
**Allowed values**: `"A"` (Energetic), `"B"` (Smooth), `"C"` (Dramatic).

### `config_data.assets` (Optional)
Allows overriding default global assets.
* **`bg_music`** *(string, optional)*: An S3 MinIO path pointing to a valid audio file (e.g. `.mp3`). If not provided, the worker defaults to its local `bg_music.mp3`.
* **`logo`** *(string, optional)*: An S3 MinIO path pointing to an image file (e.g. `.png`, `.webp`) used in the outro CTA screen. If not provided, defaults to the local `logo.webp`.

### `config_data.input_json`
Defines the text and structure of the video frames.
* **`intro_text`** *(string)*: The text displayed during the first 3 seconds (Hook / Intro).
* **`outro_text`** *(string)*: The text displayed in the final CTA screen.
* **`products`** *(array of objects)*: Must contain between **2 and 10** items.
  * **`image`** *(string)*: S3 MinIO URL for the product image.
  * **`text`** *(string)*: The display name or brief description of the product.
  * **`hook`** *(string)*: A short, catchy badge text (e.g., "Sale 50%", "Mới").

## Processing Behavior
1. The Celery worker's `prepare_fn` will scan `plugins`, `input_json.products`, and `assets`.
2. Any string containing an MinIO prefix (`s3://`) will be downloaded locally.
3. The paths in `config_data` will be subsequently modified to point to the local disk before being passed to the `slideshow_engine`.
