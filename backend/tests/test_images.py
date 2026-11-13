from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from PIL import Image
from pydantic import ValidationError

from app.main import app
from app.schemas.images import BrandAssetUpdate, ImageCheckAnalysis
from app.services.image_processing import process_image


def make_png_bytes(size: tuple[int, int] = (24, 16)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, color=(74, 35, 145)).save(output, format="PNG")
    return output.getvalue()


def test_process_image_returns_verified_metadata_and_palette():
    content = make_png_bytes()
    result = process_image(content, r"C:\\uploads\\brand-logo.png")

    assert result["original_filename"] == "brand-logo.png"
    assert result["mime_type"] == "image/png"
    assert result["image_format"] == "PNG"
    assert result["width"] == 24
    assert result["height"] == 16
    assert len(result["sha256_hash"]) == 64
    assert result["dominant_colors"][0]["hex"] == "#4A2391"
    assert result["dominant_colors"][0]["percentage"] == 100.0


def test_process_image_strips_path_from_filename():
    result = process_image(make_png_bytes(), "../../secret/logo.png")
    assert result["original_filename"] == "logo.png"


def test_process_image_rejects_non_image_bytes():
    with pytest.raises(HTTPException) as error:
        process_image(b"not an image", "broken.png")
    assert error.value.status_code == 422


def test_process_image_rejects_unsupported_svg_or_gif():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'
    with pytest.raises(HTTPException) as error:
        process_image(svg, "logo.svg")
    assert error.value.status_code == 422

    gif_output = BytesIO()
    Image.new("RGB", (2, 2), color="red").save(gif_output, format="GIF")
    with pytest.raises(HTTPException) as gif_error:
        process_image(gif_output.getvalue(), "animated.gif")
    assert gif_error.value.status_code == 415


def test_process_image_rejects_oversized_upload_before_decoding():
    with pytest.raises(HTTPException) as error:
        process_image(b"x" * (8 * 1024 * 1024 + 1), "large.png")
    assert error.value.status_code == 413


def test_brand_asset_update_rejects_blank_name():
    with pytest.raises(ValidationError):
        BrandAssetUpdate(asset_name="  ")


def test_image_check_analysis_shape():
    analysis = ImageCheckAnalysis.model_validate(
        {
            "asset_match_status": "no_exact_match",
            "matched_asset": None,
            "dominant_colors": [{"hex": "#4A2391", "percentage": 100.0}],
            "alt_text_status": "missing",
            "findings": [],
            "limitations": ["Exact hash only."],
        }
    )
    assert analysis.asset_match_status.value == "no_exact_match"
    assert analysis.dominant_colors[0].hex == "#4A2391"


def test_image_asset_routes_require_authentication():
    workspace_id = uuid4()
    with TestClient(app) as client:
        assets = client.get(f"/api/v1/workspaces/{workspace_id}/brand-assets")
        checks = client.get(f"/api/v1/workspaces/{workspace_id}/image-checks")

    assert assets.status_code == 401
    assert checks.status_code == 401
