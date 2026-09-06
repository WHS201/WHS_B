import json
import os
from datetime import date
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from app.errors.exceptions import BusinessException
from app.extensions import db
from app.models.deposits_savings import (EarlyTerminationRateRule, FinancialProduct,
    FinancialProductOption, ProductPreferenceCondition)
from app.services.preference_condition_parser import parse_preference_conditions

BASE_URL = "https://finlife.fss.or.kr/finlifeapi"
TARGET_BANKS = {"국민은행":"KB국민은행", "신한은행":"신한은행", "주식회사 하나은행":"하나은행",
                "우리은행":"우리은행", "농협은행주식회사":"NH농협은행",
                "주식회사 케이뱅크":"케이뱅크", "주식회사 카카오뱅크":"카카오뱅크",
                "토스뱅크 주식회사":"토스뱅크"}
ENDPOINTS = {"DEPOSIT":"depositProductsSearch.json", "SAVING":"savingProductsSearch.json"}


def _fetch(endpoint, page=1):
    key = os.environ.get("FSS_API_KEY")
    if not key: raise BusinessException(code="FSS_API_KEY_MISSING", message="금융감독원 API 키가 설정되지 않았습니다.", status_code=503)
    url = f"{BASE_URL}/{endpoint}?" + urlencode({"auth":key,"topFinGrpNo":"020000","pageNo":page})
    try:
        with urlopen(url, timeout=20) as response: result = json.load(response)["result"]
    except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as error:
        raise BusinessException(code="FSS_API_UNAVAILABLE", message="금융감독원 API 호출에 실패했습니다.", status_code=503) from error
    if result.get("err_cd") != "000": raise BusinessException(code="FSS_API_ERROR", message=result.get("err_msg","금융감독원 API 오류입니다."), status_code=502)
    return result


def _fetch_all(endpoint):
    first = _fetch(endpoint, 1)
    bases = list(first.get("baseList", []))
    options = list(first.get("optionList", []))
    for page in range(2, int(first.get("max_page_no") or 1) + 1):
        result = _fetch(endpoint, page)
        bases.extend(result.get("baseList", []))
        options.extend(result.get("optionList", []))
    return bases, options


def sync_products():
    seen, created, updated, options_count = set(), 0, 0, 0
    try:
        for product_type, endpoint in ENDPOINTS.items():
            bases, option_rows = _fetch_all(endpoint)
            target_bases = [
                raw for raw in bases
                if raw.get("kor_co_nm") in TARGET_BANKS
            ]
            target_product_keys = {
                (raw.get("fin_co_no"), raw.get("fin_prdt_cd"))
                for raw in target_bases
            }
            option_product_keys = {
                (raw.get("fin_co_no"), raw.get("fin_prdt_cd"))
                for raw in option_rows
            }
            if not target_product_keys or not target_product_keys.issubset(
                option_product_keys
            ):
                raise BusinessException(
                    code="FSS_API_INCOMPLETE",
                    message="금융감독원 상품 옵션 응답이 불완전합니다.",
                    status_code=502,
                )
            options = {}
            for raw in option_rows: options.setdefault((raw["fin_co_no"],raw["fin_prdt_cd"]),[]).append(raw)
            for raw in target_bases:
                code = f'{raw["fin_co_no"]}:{raw["fin_prdt_cd"]}'; seen.add(code)
                product = FinancialProduct.query.filter_by(external_product_code=code).first()
                if product is None: product=FinancialProduct(external_product_code=code); db.session.add(product); created+=1
                else: updated+=1
                if not product.sync_locked:
                    end=raw.get("dcls_end_day"); product.is_active=not end or end>=date.today().strftime("%Y%m%d")
                    product.bank_name=TARGET_BANKS[raw["kor_co_nm"]]; product.product_name=raw["fin_prdt_nm"]
                    product.product_type=product_type; product.description=raw.get("etc_note"); product.join_target=raw.get("join_member")
                db.session.flush()
                active_option_ids = set()
                for item in options.get((raw["fin_co_no"],raw["fin_prdt_cd"]),[]):
                    try: term=int(item["save_trm"])
                    except (TypeError,ValueError): continue
                    method="COMPOUND" if item.get("intr_rate_type")=="M" else "SIMPLE"
                    option=FinancialProductOption.query.filter_by(product_id=product.product_id,term_months=term,interest_method=method).first()
                    if option is None: option=FinancialProductOption(product_id=product.product_id,term_months=term,interest_method=method); db.session.add(option)
                    if option.sync_locked:
                        active_option_ids.add(option.option_id)
                        options_count += 1
                        continue
                    base=Decimal(str(item.get("intr_rate") or 0)); maximum=max(base,Decimal(str(item.get("intr_rate2") or 0)))
                    option.base_interest_rate=base; option.max_interest_rate=maximum; option.is_active=product.is_active
                    min_amount=100000 if product_type=="DEPOSIT" else 10000
                    max_amount=int(raw.get("max_limit") or 100000000)
                    option.min_amount=1 if min_amount > max_amount else min_amount
                    option.max_amount=max_amount; db.session.flush(); options_count+=1
                    active_option_ids.add(option.option_id)
                    bonus=maximum-base
                    parsed_conditions = parse_preference_conditions(raw.get("spcl_cnd"), bonus)
                    active_codes = {item["condition_code"] for item in parsed_conditions}
                    ProductPreferenceCondition.query.filter(
                        ProductPreferenceCondition.option_id == option.option_id,
                        ProductPreferenceCondition.condition_code.like("FSS_%"),
                        ProductPreferenceCondition.condition_code.notin_(active_codes),
                    ).update({ProductPreferenceCondition.is_active:False}, synchronize_session=False)
                    for parsed in parsed_conditions:
                        condition=ProductPreferenceCondition.query.filter_by(
                            option_id=option.option_id,
                            condition_code=parsed["condition_code"],
                        ).first()
                        if condition is None:
                            condition=ProductPreferenceCondition(
                                option_id=option.option_id,
                                condition_code=parsed["condition_code"],
                            )
                            db.session.add(condition)
                        condition.condition_name=parsed["condition_name"]
                        condition.description=parsed["description"]
                        condition.additional_interest_rate=parsed["additional_interest_rate"]
                        condition.is_active=True
                    rule=EarlyTerminationRateRule.query.filter_by(option_id=option.option_id,is_assumed=True).first()
                    if rule is None: rule=EarlyTerminationRateRule(option_id=option.option_id,minimum_holding_days=0,calculation_type="FIXED_RATE",is_assumed=True); db.session.add(rule)
                    rule.rate_value=Decimal("0.1000"); rule.description="금감원 API 미제공으로 적용한 임시값"
                if not active_option_ids:
                    raise BusinessException(
                        code="FSS_API_INCOMPLETE",
                        message="금융감독원 상품 옵션 응답이 불완전합니다.",
                        status_code=502,
                    )
                stale_options = FinancialProductOption.query.filter(
                    FinancialProductOption.product_id == product.product_id,
                    FinancialProductOption.is_active.is_(True),
                )
                if active_option_ids:
                    stale_options = stale_options.filter(
                        FinancialProductOption.option_id.notin_(active_option_ids)
                    )
                stale_options.update(
                    {FinancialProductOption.is_active: False},
                    synchronize_session=False,
                )
        unseen_products = FinancialProduct.query.filter(
            FinancialProduct.external_product_code.contains(":"),
            FinancialProduct.external_product_code.notin_(seen),
        )
        unseen_product_ids = [
            product_id
            for (product_id,) in unseen_products.with_entities(
                FinancialProduct.product_id
            ).all()
        ]
        deactivated = FinancialProduct.query.filter(
            FinancialProduct.product_id.in_(unseen_product_ids),
            FinancialProduct.is_active.is_(True),
        ).update(
            {FinancialProduct.is_active: False},
            synchronize_session=False,
        )
        if unseen_product_ids:
            FinancialProductOption.query.filter(
                FinancialProductOption.product_id.in_(unseen_product_ids),
                FinancialProductOption.is_active.is_(True),
            ).update(
                {FinancialProductOption.is_active: False},
                synchronize_session=False,
            )
        db.session.commit(); return {"created_count":created,"updated_count":updated,"option_count":options_count,"deactivated_count":deactivated}
    except Exception: db.session.rollback(); raise
