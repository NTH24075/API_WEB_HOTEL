from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.hotels import router as hotels_router

app = FastAPI(title="Hotel Demo with Amadeus")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(hotels_router)


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


@app.get("/hotels/{hotel_id}")
def hotel_detail_page(
    request: Request,
    hotel_id: str,
    check_in: str = "2026-04-08",
    adults: int = 2,
):
    return templates.TemplateResponse(
        request=request,
        name="hotel_detail.html",
        context={
            "hotel_id": hotel_id,
            "check_in": check_in,
            "adults": adults,
        },
    )