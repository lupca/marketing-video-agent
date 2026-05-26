"""
Defensive healer for the ``slideshow`` worker type.

Ensures ``input_json`` with ``products``, ``intro_text``, and ``outro_text``
are present with sensible defaults.
"""

from typing import Dict, Any, List


def heal_slideshow(draft_params: Dict[str, Any], sentences: List[str], title: str) -> Dict[str, Any]:
    """Logic sửa lỗi phòng thủ cho worker slideshow."""
    if "input_json" not in draft_params or not isinstance(draft_params["input_json"], dict):
        draft_params["input_json"] = {}
    input_json = draft_params["input_json"]

    if "products" in draft_params and "products" not in input_json:
        input_json["products"] = draft_params.pop("products")

    if "intro_text" not in input_json or not input_json["intro_text"]:
        input_json["intro_text"] = title or "Chào mừng đến với " + (sentences[0][:20] if sentences else "Video")
    if "outro_text" not in input_json or not input_json["outro_text"]:
        input_json["outro_text"] = "Mua ngay tại giỏ hàng bên dưới!"

    if "products" not in input_json or not isinstance(input_json["products"], list) or len(input_json["products"]) == 0:
        products = []
        for idx, sen in enumerate(sentences[:4]):
            products.append({
                "image": f"https://images.unsplash.com/photo-{1523275335684 + idx * 1000}-37898b6baf30?w=500",
                "text": sen,
                "hook": f"Đặc điểm {idx+1}",
            })
        input_json["products"] = products

    for idx, prod in enumerate(input_json["products"]):
        if not isinstance(prod, dict):
            continue
        if "image" not in prod or not prod["image"]:
            prod["image"] = f"https://images.unsplash.com/photo-{1523275335684 + idx * 100}-37898b6baf30?w=500"
        if "text" not in prod or not prod["text"]:
            prod["text"] = sentences[idx % len(sentences)]
        if "hook" not in prod or not prod["hook"]:
            prod["hook"] = "Khám phá ngay"
    return draft_params
