from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.schemas.investment import OrderCreateSchema, PriceQuerySchema
from app.services import investment_service


investments_bp = Blueprint(
    "investments",
    __name__,
    url_prefix="/api/investments",
)


# ----------------------------------------------------------------
# 종목 목록 조회

@investments_bp.get("/assets")
@jwt_required()
def get_assets():
    market = request.args.get("market")
    search = request.args.get("q", "").strip()

    result = investment_service.get_assets(
        market=market,
        search=search,
    )

    return jsonify({
        "success": True,
        "data": result,
        "message": "종목 목록 조회에 성공했습니다.",
    }), 200


# ----------------------------------------------------------------
# 현재가 조회

@investments_bp.get("/price")
@jwt_required()
def get_price():
    # Query Parameter 검증
    query_params = PriceQuerySchema().load({
        "symbol": request.args.get("symbol"),
        "market": request.args.get("market"),
    })

    # 외부 시장 데이터 조회
    result = investment_service.get_price(
        symbol=query_params["symbol"],
        market=query_params["market"],
    )

    # Response 반환
    return jsonify({
        "success": True,
        "data": result,
        "message": "현재가 조회에 성공했습니다.",
    }), 200


# ----------------------------------------------------------------
# 주문

@investments_bp.post("/orders")
@jwt_required()
def create_order():
    # Request Body 검증
    payload = OrderCreateSchema().load(
        request.get_json(silent=True) or {}
    )

    # 사용자 식별자는 클라이언트 값이 아닌 JWT에서 가져온다
    user_id = int(get_jwt_identity())

    # 주문 체결 처리
    result = investment_service.create_order(
        user_id=user_id,
        symbol=payload["symbol"],
        market=payload["market"],
        side=payload["side"],
        quantity=payload["quantity"],
    )

    # Response 반환
    return jsonify({
        "success": True,
        "data": result,
        "message": "주문이 체결되었습니다.",
    }), 201