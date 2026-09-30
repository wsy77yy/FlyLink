from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator


CREDIT_SCORE_MIN = 300
CREDIT_SCORE_MAX = 1000
REVIEW_SCORE_MIN = 1
REVIEW_SCORE_MAX = 5
ORDER_BUDGET_MIN = Decimal('100.00')
ORDER_BUDGET_MAX = Decimal('9999999999.99')
SALARY_MIN = 3000
SALARY_MAX = 1000000
MONEY_10_MAX = Decimal('99999999.99')
MONEY_12_MAX = Decimal('9999999999.99')


credit_score_validators = [
    MinValueValidator(CREDIT_SCORE_MIN),
    MaxValueValidator(CREDIT_SCORE_MAX),
]
review_score_validators = [
    MinValueValidator(REVIEW_SCORE_MIN),
    MaxValueValidator(REVIEW_SCORE_MAX),
]
order_budget_validators = [
    MinValueValidator(ORDER_BUDGET_MIN),
    MaxValueValidator(ORDER_BUDGET_MAX),
]
salary_validators = [
    MinValueValidator(SALARY_MIN),
    MaxValueValidator(SALARY_MAX),
]
