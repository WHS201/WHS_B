from datetime import datetime

from app.extensions import db
from app.models.base import TimestampMixin


class FinancialProduct(TimestampMixin, db.Model):
    __tablename__ = "financial_products"
    product_id = db.Column(db.Integer, primary_key=True)
    external_product_code = db.Column(db.String(100), nullable=False, unique=True)
    bank_name = db.Column(db.String(100), nullable=False)
    product_name = db.Column(db.String(200), nullable=False)
    product_type = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text)
    join_target = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sync_locked = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("0"))
    options = db.relationship("FinancialProductOption", back_populates="product",
                              cascade="all, delete-orphan", lazy="selectin")


class FinancialProductOption(db.Model):
    __tablename__ = "financial_product_options"
    option_id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("financial_products.product_id"), nullable=False)
    term_months = db.Column(db.Integer, nullable=False)
    base_interest_rate = db.Column(db.Numeric(6, 4), nullable=False)
    max_interest_rate = db.Column(db.Numeric(6, 4), nullable=False)
    interest_method = db.Column(db.String(30), nullable=False, default="SIMPLE")
    min_amount = db.Column(db.BigInteger, nullable=False)
    max_amount = db.Column(db.BigInteger, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sync_locked = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("0"))
    product = db.relationship("FinancialProduct", back_populates="options")
    preference_conditions = db.relationship("ProductPreferenceCondition", back_populates="option",
                                             cascade="all, delete-orphan", lazy="selectin")
    early_termination_rules = db.relationship("EarlyTerminationRateRule", back_populates="option",
                                              cascade="all, delete-orphan", lazy="selectin")
    __table_args__ = (db.UniqueConstraint("product_id", "term_months", "interest_method",
                                         name="uq_product_option_term_method"),)


class ProductPreferenceCondition(TimestampMixin, db.Model):
    __tablename__ = "product_preference_conditions"
    condition_id = db.Column(db.Integer, primary_key=True)
    option_id = db.Column(db.Integer, db.ForeignKey("financial_product_options.option_id"), nullable=False)
    condition_code = db.Column(db.String(50), nullable=False)
    condition_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(1000))
    additional_interest_rate = db.Column(db.Numeric(6, 4), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    option = db.relationship("FinancialProductOption", back_populates="preference_conditions")
    __table_args__ = (db.UniqueConstraint("option_id", "condition_code",
                                         name="uq_option_condition_code"),)


class EarlyTerminationRateRule(TimestampMixin, db.Model):
    __tablename__ = "early_termination_rate_rules"
    early_termination_rule_id = db.Column(db.Integer, primary_key=True)
    option_id = db.Column(db.Integer, db.ForeignKey("financial_product_options.option_id"), nullable=False)
    minimum_holding_days = db.Column(db.Integer, nullable=False)
    maximum_holding_days = db.Column(db.Integer)
    calculation_type = db.Column(db.String(30), nullable=False)
    rate_value = db.Column(db.Numeric(8, 4), nullable=False)
    is_assumed = db.Column(db.Boolean, nullable=False, default=False)
    description = db.Column(db.String(500))
    option = db.relationship("FinancialProductOption", back_populates="early_termination_rules")


class Deposit(TimestampMixin, db.Model):
    __tablename__ = "deposits"
    deposit_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("financial_products.product_id"), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey("financial_product_options.option_id"), nullable=False)
    principal = db.Column(db.BigInteger, nullable=False)
    applied_interest_rate = db.Column(db.Numeric(6, 4), nullable=False)
    interest_method = db.Column(db.String(30), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    maturity_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="ACTIVE", index=True)
    gross_interest = db.Column(db.BigInteger)
    tax_rate = db.Column(db.Numeric(6, 4))
    tax_amount = db.Column(db.BigInteger)
    net_interest = db.Column(db.BigInteger)
    payout_amount = db.Column(db.BigInteger)
    applied_early_termination_rate = db.Column(db.Numeric(6, 4))
    matured_at = db.Column(db.DateTime)
    terminated_at = db.Column(db.DateTime)
    product = db.relationship("FinancialProduct")
    option = db.relationship("FinancialProductOption")
    preference_conditions = db.relationship("DepositPreferenceCondition", back_populates="deposit",
                                            cascade="all, delete-orphan", lazy="selectin")


class DepositPreferenceCondition(db.Model):
    __tablename__ = "deposit_preference_conditions"
    deposit_preference_condition_id = db.Column(db.Integer, primary_key=True)
    deposit_id = db.Column(db.Integer, db.ForeignKey("deposits.deposit_id"), nullable=False)
    condition_id = db.Column(db.Integer, db.ForeignKey("product_preference_conditions.condition_id"), nullable=False)
    condition_name = db.Column(db.String(100), nullable=False)
    additional_interest_rate = db.Column(db.Numeric(6, 4), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    deposit = db.relationship("Deposit", back_populates="preference_conditions")


class Saving(TimestampMixin, db.Model):
    __tablename__ = "savings"
    saving_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("financial_products.product_id"), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey("financial_product_options.option_id"), nullable=False)
    monthly_amount = db.Column(db.BigInteger, nullable=False)
    scheduled_payment_count = db.Column(db.Integer, nullable=False)
    applied_interest_rate = db.Column(db.Numeric(6, 4), nullable=False)
    interest_method = db.Column(db.String(30), nullable=False)
    payment_day = db.Column(db.Integer, nullable=False)
    next_payment_date = db.Column(db.Date)
    start_date = db.Column(db.Date, nullable=False)
    maturity_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="ACTIVE", index=True)
    total_paid_principal = db.Column(db.BigInteger, nullable=False, default=0)
    gross_interest = db.Column(db.BigInteger)
    tax_rate = db.Column(db.Numeric(6, 4))
    tax_amount = db.Column(db.BigInteger)
    net_interest = db.Column(db.BigInteger)
    payout_amount = db.Column(db.BigInteger)
    applied_early_termination_rate = db.Column(db.Numeric(6, 4))
    matured_at = db.Column(db.DateTime)
    terminated_at = db.Column(db.DateTime)
    product = db.relationship("FinancialProduct")
    option = db.relationship("FinancialProductOption")
    preference_conditions = db.relationship("SavingPreferenceCondition", back_populates="saving",
                                            cascade="all, delete-orphan", lazy="selectin")
    payments = db.relationship("SavingPayment", back_populates="saving",
                               cascade="all, delete-orphan", lazy="selectin")


class SavingPreferenceCondition(db.Model):
    __tablename__ = "saving_preference_conditions"
    saving_preference_condition_id = db.Column(db.Integer, primary_key=True)
    saving_id = db.Column(db.Integer, db.ForeignKey("savings.saving_id"), nullable=False)
    condition_id = db.Column(db.Integer, db.ForeignKey("product_preference_conditions.condition_id"), nullable=False)
    condition_name = db.Column(db.String(100), nullable=False)
    additional_interest_rate = db.Column(db.Numeric(6, 4), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    saving = db.relationship("Saving", back_populates="preference_conditions")


class SavingPayment(db.Model):
    __tablename__ = "saving_payments"
    payment_id = db.Column(db.Integer, primary_key=True)
    saving_id = db.Column(db.Integer, db.ForeignKey("savings.saving_id"), nullable=False)
    payment_sequence = db.Column(db.Integer, nullable=False)
    payment_year_month = db.Column(db.String(7), nullable=False)
    scheduled_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.BigInteger, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    processed_at = db.Column(db.DateTime)
    saving = db.relationship("Saving", back_populates="payments")
    __table_args__ = (db.UniqueConstraint("saving_id", "payment_sequence",
                                         name="uq_saving_payment_sequence"),)


class LedgerTransaction(db.Model):
    __tablename__ = "ledger_transactions"
    ledger_transaction_id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.account_id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.BigInteger, nullable=False)
    balance_after = db.Column(db.BigInteger, nullable=False)
    reference_type = db.Column(db.String(50), nullable=False)
    reference_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    entries = db.relationship("LedgerEntry", back_populates="transaction",
                              cascade="all, delete-orphan")


class LedgerEntry(db.Model):
    __tablename__ = "ledger_entries"
    ledger_entry_id = db.Column(db.Integer, primary_key=True)
    ledger_transaction_id = db.Column(db.Integer, db.ForeignKey("ledger_transactions.ledger_transaction_id"), nullable=False)
    entry_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.BigInteger, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    transaction = db.relationship("LedgerTransaction", back_populates="entries")
