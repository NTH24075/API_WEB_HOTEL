import random
from typing import Any

_ROOM_TEMPLATES = [
    ("Phong Standard", "Phong tieu chuan, day du tien nghi co ban.", 2, 600_000, "1 giuong doi, wifi, may lanh", "Mien phi huy truoc 24h."),
    ("Phong Superior", "Phong rong hon Standard, co ban cong nhin ra thanh pho.", 2, 900_000, "1 giuong queen, wifi, may lanh, TV", "Mien phi huy truoc 48h."),
    ("Phong Deluxe", "Phong cao cap, noi that sang trong, tam nhin dep.", 2, 1_400_000, "1 giuong king, wifi, bon tam", "Mien phi huy truoc 48h."),
    ("Phong Deluxe Twin", "Danh cho 2 nguoi, 2 giuong don thoai mai.", 2, 1_200_000, "2 giuong don, wifi, may lanh", "Mien phi huy truoc 24h."),
    ("Phong Family", "Rong rai, phu hop gia dinh co tre nho.", 4, 1_800_000, "1 giuong king + 2 giuong don, wifi", "Khong hoan tien sau khi dat."),
    ("Phong Suite", "Suite hang sang, phong khach rieng, minibar.", 2, 3_200_000, "1 giuong king, phong khach, bon suc", "Mien phi huy truoc 72h."),
    ("Phong Junior Suite", "Khong gian mo, khu nghi ngoi va lam viec tach biet.", 2, 2_100_000, "1 giuong king, sofa, wifi toc do cao", "Mien phi huy truoc 48h."),
    ("Phong Executive", "Danh cho khach cong tac, co khu lam viec chuyen nghiep.", 2, 1_600_000, "1 giuong king, ban lam viec, wifi", "Mien phi huy truoc 24h."),
    ("Phong Connecting", "2 phong lien nhau, ly tuong cho nhom hoac gia dinh lon.", 4, 2_400_000, "2 giuong doi ket noi, wifi", "Mien phi huy truoc 48h."),
    ("Phong Penthouse", "Penthouse tang thuong, tam nhin toan canh 360 do.", 2, 5_500_000, "1 giuong king, san thuong rieng, bon suc", "Khong hoan tien sau khi dat."),
]


def _random_price_multiplier(hotel_id: int) -> float:
    rng = random.Random(hotel_id * 1337 + 42)
    return round(rng.uniform(0.7, 1.8), 2)


def build_default_room_offers(hotel_id: int) -> list[dict[str, Any]]:
    rng = random.Random(hotel_id * 7919 + 13)
    num_rooms = rng.randint(3, 5)
    chosen = rng.sample(_ROOM_TEMPLATES, k=min(num_rooms, len(_ROOM_TEMPLATES)))
    multiplier = _random_price_multiplier(hotel_id)

    offers: list[dict[str, Any]] = []
    for idx, (room_type, description, capacity, base_price, amenities, policy) in enumerate(chosen, start=1):
        raw_price = base_price * multiplier
        price = round(raw_price / 50_000) * 50_000
        price = max(300_000, price)
        offers.append(
            {
                "offer_id": f"default-{hotel_id}-{idx}",
                "room_type": room_type,
                "description": description,
                "capacity": capacity,
                "price_total": float(price),
                "price_base": float(price),
                "currency": "VND",
                "available_quantity": rng.randint(1, 8),
                "cancellation_policy": policy,
                "amenities": amenities,
                "beds": 1,
                "bed_type": "Standard",
                "payment_type": "Pay at hotel",
            }
        )
    return offers


def get_default_price_from(hotel_id: int) -> float:
    offers = build_default_room_offers(hotel_id)
    return min(float(item["price_total"]) for item in offers)
