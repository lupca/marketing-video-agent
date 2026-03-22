
```json
{
    "input_json": {
      "intro_text": "Top sản phẩm bán chạy",
      "outro_text": "Mua ngay hôm nay!",
      "products": [
        { "image": "product1.jpg", "text": "Sản phẩm 1", "hook": "Giảm 50%" },
        { "image": "product2.jpg", "text": "Sản phẩm 2", "hook": "Mới nhất" }
      ]
    }
}
```


### input_json Schema

```json
{
  "intro_text": "string — Text shown in intro hook (required)",
  "outro_text": "string — CTA text in outro (required)",
  "products": [
    {
      "image": "string — filename matching input_images order",
      "text": "string — product name/description",
      "hook": "string — short hook/badge text"
    }
  ]
}
```

- Products: min 2, max 10
- Variant profiles: A (energetic), B (smooth), C (dramatic)

