import os
import json
import pathlib
import requests


API_BASE = os.getenv("API_BASE", "http://127.0.0.1/api").rstrip("/")

KC_BASE = os.getenv("KC_BASE", "http://127.0.0.1:8081").rstrip("/")   # Keycloak exposed port
KC_REALM = os.getenv("KC_REALM", "alpstore")
KC_CLIENT_ID = os.getenv("KC_CLIENT_ID", "alpstore-frontend")        
KC_CLIENT_SECRET = os.getenv("KC_CLIENT_SECRET", "").strip()    

KC_USERNAME = os.getenv("KC_USERNAME", "").strip()
KC_PASSWORD = os.getenv("KC_PASSWORD", "").strip()

if not KC_USERNAME or not KC_PASSWORD:
    raise SystemExit("Missing KC_USERNAME / KC_PASSWORD env vars (KC_USERNAME, KC_PASSWORD).")


# Check Keycloak token via Password Grant
def get_token_password_grant() -> str:
    token_url = f"{KC_BASE}/realms/{KC_REALM}/protocol/openid-connect/token"
    data = {
        "grant_type": "password",
        "client_id": KC_CLIENT_ID,
        "username": KC_USERNAME,
        "password": KC_PASSWORD,
    }
    if KC_CLIENT_SECRET:
        data["client_secret"] = KC_CLIENT_SECRET

    r = requests.post(token_url, data=data, timeout=15)
    if r.status_code >= 300:
        raise RuntimeError(f"Keycloak token failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


# Upload image to backend, get URL
def upload_image(path: str) -> str:
    p = pathlib.Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Missing image file: {path}")

    with p.open("rb") as f:
        files = {"file": (p.name, f, "application/octet-stream")}
        r = requests.post(f"{API_BASE}/upload-image", files=files, timeout=30)

    if r.status_code >= 300:
        raise RuntimeError(f"upload-image failed: {r.status_code} {r.text}")

    return r.json()["url"]  # /static/uploads/...

# Add product via backend API
def add_product(token: str, prod: dict):
    r = requests.post(
        f"{API_BASE}/add-product",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        data=json.dumps(prod),
        timeout=30,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"add-product failed: {r.status_code} {r.text}")
    return r.json()

# Reset products via backend admin route
def reset_products(token: str):
    r = requests.post(
        f"{API_BASE}/admin/reset-products",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        data=json.dumps({"confirm": "yes"}),
        timeout=30,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"reset-products failed: {r.status_code} {r.text}")
    return r.json()


def main():
    print("[1/4] Getting token from Keycloak...")
    token = get_token_password_grant()
    print("  token OK")

    if os.getenv("DO_RESET", "true").lower() in ("1", "true", "yes"):
        print("[2/4] Resetting products...")
        print(" ", reset_products(token))

    print("[3/4] Seeding products...")


    products = [
        #  BOOTS 
        {
            "name": "AlpineGrip GTX Boot",
            "description": "Waterproof Gore-Tex hiking boots with Vibram outsole, great for rocky alpine trails.",
            "price": 899.90,
            "category": "Boots",
            "stock": 7,
            "image_path": "./seed_images/boots_alpinegrip_gtx.jpg",
        },
        {
            "name": "MontBlanc Ridge Pro",
            "description": "Stiff, crampon-compatible mountaineering boots for snow and mixed terrain.",
            "price": 1299.50,
            "category": "Boots",
            "stock": 4,
            "image_path": "./seed_images/boots_montblanc_ridge_pro.jpg",
        },

        #  BACKPACKS 
        {
            "name": "SummitFlow 35L Backpack",
            "description": "Light 35L pack with hydration sleeve, trekking pole holders, and breathable back panel.",
            "price": 429.00,
            "category": "Backpacks",
            "stock": 10,
            "image_path": "./seed_images/backpack_summitflow_35l.jpg",
        },
        {
            "name": "GlacierHaul 55L Trek Pack",
            "description": "55L trekking backpack with adjustable suspension and rain cover included.",
            "price": 649.00,
            "category": "Backpacks",
            "stock": 6,
            "image_path": "./seed_images/backpack_glacierhaul_55l.jpg",
        },

        #  TENTS 
        {
            "name": "StormShield 2P Tent",
            "description": "Four-season 2-person tent with strong poles and excellent wind stability.",
            "price": 1149.00,
            "category": "Tents",
            "stock": 5,
            "image_path": "./seed_images/tent_stormshield_2p.jpg",
        },
        {
            "name": "PineLite 1P Ultralight",
            "description": "Ultralight 1-person tent for fastpacking and solo hikes, compact and quick to pitch.",
            "price": 899.00,
            "category": "Tents",
            "stock": 8,
            "image_path": "./seed_images/tent_pinelite_1p_ultralight.jpg",
        },

        #  JACKETS 
        {
            "name": "NorthWind Shell Jacket",
            "description": "3-layer hardshell jacket (waterproof + breathable) for rain, wind, and alpine storms.",
            "price": 799.00,
            "category": "Jackets",
            "stock": 12,
            "image_path": "./seed_images/jacket_northwind_shell.jpg",
        },
        {
            "name": "ThermaPeak Down Jacket",
            "description": "Warm down jacket with packable design, ideal for cold belays or summit breaks.",
            "price": 699.00,
            "category": "Jackets",
            "stock": 9,
            "image_path": "./seed_images/jacket_thermapeak_down.jpg",
        },

        #  PANTS 
        {
            "name": "RockTraverse Softshell Pants",
            "description": "Durable softshell pants with stretch fabric and reinforced knees for scrambling.",
            "price": 349.00,
            "category": "Pants",
            "stock": 14,
            "image_path": "./seed_images/pants_rocktraverse_softshell.jpg",
        },
        {
            "name": "SnowLine Insulated Pants",
            "description": "Insulated mountain pants with water-resistant outer layer, great for winter hikes.",
            "price": 459.00,
            "category": "Pants",
            "stock": 7,
            "image_path": "./seed_images/pants_snowline_insulated.jpg",
        },

        {
            "name": "TrailEdge Mid GTX",
            "description": "Versatile mid-cut hiking boots, supportive ankle design and grippy sole.",
            "price": 699.00,
            "category": "Boots",
            "stock": 11,
            "image_path": "./seed_images/boots_trailedge_mid_gtx.jpg",
        },
        {
            "name": "RidgeRunner 25L Daypack",
            "description": "Compact 25L daypack for short hikes, with chest strap and ventilated back.",
            "price": 299.00,
            "category": "Backpacks",
            "stock": 15,
            "image_path": "./seed_images/backpack_ridgerunner_25l.jpg",
        },
    ]

    for i, p in enumerate(products, start=1):
        print(f"  [{i}/{len(products)}] uploading image: {p['image_path']}")
        img_url = upload_image(p["image_path"])

        payload = {
            "name": p["name"],
            "description": p["description"],
            "price": p["price"],
            "category": p["category"],
            "stock": p["stock"],
            "imageUrl": img_url,
        }

        out = add_product(token, payload)
        print("     added:", out)

    print("[4/4] Done.")


if __name__ == "__main__":
    main()
