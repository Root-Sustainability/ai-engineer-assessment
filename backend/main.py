from typing import List, Annotated, Sequence

from fastapi import FastAPI, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from orm_models import AddressORM
from database import Base, engine, SessionLocal
from models import Address, AddressCreate, AddressesRefresh, AddressUpdate
from similarity import address_similarity
from mapbox_client import MapboxClient

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Address Assessment Backend",
    description="Minimal backend for the Root Sustainability AI/ML Engineer assessment.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

DBSession = Annotated[Session, Depends(get_db_session)]
mapbox_client = MapboxClient()


def score(address: str, matched_address: str) -> float:
    similarity_score = address_similarity(address, matched_address)
    return float(similarity_score)


def lookup_and_score(address: str) -> tuple[str, float]:
    matched_address = mapbox_client.geocode_best_match(address)
    similarity_score = score(address, matched_address) if matched_address else 0.0
    return matched_address, similarity_score


@app.get("/addresses", response_model=List[Address])
def get_addresses(session: DBSession) -> List[Address]:
    addresses: Sequence[AddressORM] = session.scalars(select(AddressORM)).all()
    return [address.to_pydantic() for address in addresses]


@app.get("/addresses/{id}", response_model=Address)
def get_address(session: DBSession, id: int) -> Address:
    address = session.scalars(select(AddressORM).where(AddressORM.id == id)).one_or_none()
    return address.to_pydantic()


@app.post("/addresses", response_model=Address, status_code=201)
def create_address(session: DBSession, payload: AddressCreate) -> Address:
    match, score = lookup_and_score(payload.address)
    session.add(address := AddressORM(address=payload.address, matched_address=match, match_score=score))
    session.commit()
    return address.to_pydantic()

@app.post("/addresses/bulk", status_code=200, response_model=List[Address])
async def bulk_upload_addresses(session: DBSession, file: UploadFile = File(...)):
    import csv
    import io

    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    
    addresses_to_process = []
    for row in reader:
        if "address" in row and row["address"]:
            addresses_to_process.append(row["address"])
    
    if not addresses_to_process:
        return []

    results = []
    chunk_size = 1000
    
    for i in range(0, len(addresses_to_process), chunk_size):
        chunk = addresses_to_process[i:i + chunk_size]
        matches = mapbox_client.geocode_batch(chunk)
        
        for address_text, match in zip(chunk, matches):
            similarity_score = score(address_text, match) if match else 0.0
            
            db_address = AddressORM(
                address=address_text, 
                matched_address=match if match else "", 
                match_score=similarity_score
            )
            session.add(db_address)

            session.commit()
            session.refresh(db_address)
            results.append(db_address.to_pydantic())
            
    return results


@app.post("/addresses/refresh", status_code=200)
def refresh_addresses(session: DBSession, payload: AddressesRefresh):
    query =select(AddressORM)
    if payload.ids is not None:
        query.where(AddressORM.id.in_(payload.ids))
    addresses: Sequence[AddressORM] = session.scalars(query).all()
    for address in addresses:
        match, score = lookup_and_score(address.address)
        address.matched_address = match
        address.match_score = score
    session.commit()
    return

@app.post("/addresses/{id}", response_model=Address, status_code=201)
def update_address(session: DBSession, id: int, payload: AddressUpdate) -> Address:
    address = session.scalars(select(AddressORM).where(AddressORM.id == id)).one_or_none()
    match, score = lookup_and_score(payload.address)
    address.address = payload.address
    address.matched_address = match
    address.match_score = score
    session.commit()
    return address.to_pydantic()

