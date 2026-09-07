import csv
from pathlib import Path

from app.extensions import db
from app.models.market import MarketAsset


# backend/kr_market_assets.csv
KR_MARKET_ASSET_CSV = (
    Path(__file__).resolve().parents[2]
    / "kr_market_assets.csv"
)


def _upsert_stock(symbol, name):
    """
    국내 상장 주식을 추가하거나 기존 정보를 갱신한다.
    """

    row = MarketAsset.query.filter_by(
        symbol=symbol,
        market="KR",
    ).first()

    if row is None:
        row = MarketAsset(
            symbol=symbol,
            name=name,
            asset_type="STOCK",
            market="KR",
            is_active=True,
        )
        db.session.add(row)

    else:
        row.name = name
        row.asset_type = "STOCK"
        row.is_active = True


def _load_kr_stock_list():
    """
    backend/kr_market_assets.csv 파일에서
    국내 상장 종목 목록을 읽어온다.
    """

    if not KR_MARKET_ASSET_CSV.exists():
        raise RuntimeError(
            f"국내 종목 CSV 파일을 찾을 수 없습니다: "
            f"{KR_MARKET_ASSET_CSV}"
        )

    assets = []

    with KR_MARKET_ASSET_CSV.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        required_columns = {
            "회사명",
            "종목코드",
        }

        if not reader.fieldnames:
            raise RuntimeError(
                "국내 종목 CSV에 헤더가 없습니다."
            )

        if not required_columns.issubset(
            set(reader.fieldnames)
        ):
            raise RuntimeError(
                "국내 종목 CSV 형식이 예상과 다릅니다."
            )

        for item in reader:
            name = str(
                item.get("회사명") or ""
            ).strip()

            symbol = str(
                item.get("종목코드") or ""
            ).strip().upper()

            if (
                not symbol
                or not name
                or len(symbol) != 6
                or not symbol.isalnum()
            ):
                continue

            assets.append(
                {
                    "symbol": symbol,
                    "name": name,
                }
            )

    return assets


def sync_kr_market_assets():
    """
    CSV에 저장된 국내 상장 주식 종목 마스터를
    market_assets 테이블과 동기화한다.

    - 신규 종목 추가
    - 기존 종목 이름 갱신
    - 현재 목록에 없는 국내 STOCK 비활성화
    - ETF는 건드리지 않음
    """

    try:
        assets = _load_kr_stock_list()

        # 잘못된/빈 CSV로 인해 기존 종목 전체가
        # 비활성화되는 사고를 방지한다.
        if len(assets) < 1000:
            raise RuntimeError(
                "국내 종목 CSV의 종목 수가 비정상적으로 적습니다. "
                f"현재 종목 수: {len(assets)}"
            )

        synced_symbols = set()

        for asset in assets:
            symbol = asset["symbol"]
            name = asset["name"]

            _upsert_stock(
                symbol=symbol,
                name=name,
            )

            synced_symbols.add(symbol)

        existing_stocks = (
            MarketAsset.query
            .filter_by(
                market="KR",
                asset_type="STOCK",
            )
            .all()
        )

        disabled = 0

        for row in existing_stocks:
            if row.symbol not in synced_symbols:
                row.is_active = False
                disabled += 1

        db.session.commit()

        return {
            "synced": len(synced_symbols),
            "disabled": disabled,
        }

    except Exception:
        db.session.rollback()
        raise