import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from secrets import token_hex

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.common.order_numbers import generate_order_no

from .models import DroneModel, DroneUnit, MaintenanceRecord, RentalOrder


logger = logging.getLogger('flylink.rental')
INSURANCE_DAILY = Decimal('38.00')


class RentalDomainError(Exception):
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _unit_serial(model):
    return f'FL-{model.pk:04d}-{token_hex(5).upper()}'


def _create_units(model, count):
    DroneUnit.objects.bulk_create([
        DroneUnit(model=model, serial_number=_unit_serial(model))
        for _ in range(count)
    ])


@transaction.atomic
def create_drone_model(*, validated_data):
    stock = validated_data.pop('stock', 1)
    model = DroneModel.objects.create(**validated_data)
    _create_units(model, stock)
    return model


@transaction.atomic
def update_drone_model(*, model, validated_data):
    desired_stock = validated_data.pop('stock', None)
    for field, value in validated_data.items():
        setattr(model, field, value)
    if validated_data:
        model.save(update_fields=list(validated_data))
    if desired_stock is not None:
        available = list(
            DroneUnit.objects.select_for_update().filter(
                model=model, status=DroneUnit.Status.AVAILABLE,
            )
        )
        if desired_stock > len(available):
            _create_units(model, desired_stock - len(available))
        elif desired_stock < len(available):
            retire = available[desired_stock:]
            for unit in retire:
                unit.status = DroneUnit.Status.RETIRED
            DroneUnit.objects.bulk_update(retire, ['status'])
    return model


@transaction.atomic
def add_unit(*, model, serial_number=None):
    return DroneUnit.objects.create(
        model=model,
        serial_number=serial_number or _unit_serial(model),
    )


@transaction.atomic
def add_maintenance(*, unit, content, cost):
    locked_unit = DroneUnit.objects.select_for_update().get(pk=unit.pk)
    record = MaintenanceRecord.objects.create(
        unit=locked_unit,
        content=content,
        cost=cost,
    )
    locked_unit.status = DroneUnit.Status.MAINTAINING
    locked_unit.save(update_fields=['status'])
    return record


def parse_rental_dates(start, end):
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except (TypeError, ValueError) as exc:
        raise RentalDomainError('租赁日期格式错误。') from exc
    if end_date < start_date:
        raise RentalDomainError('结束日期不能早于开始日期。')
    if start_date < timezone.localdate():
        raise RentalDomainError('开始日期不能早于今天。')
    if (end_date - start_date).days > 365:
        raise RentalDomainError('单次租期不能超过 366 天。')
    return start_date, end_date


@transaction.atomic
def create_rental_order(*, user, model_id, start, end, delivery_type, remark=''):
    start_date, end_date = parse_rental_dates(start, end)
    try:
        model = DroneModel.objects.get(pk=model_id)
    except DroneModel.DoesNotExist as exc:
        raise RentalDomainError('设备型号不存在。', 404) from exc
    unit = (
        DroneUnit.objects.select_for_update()
        .filter(model=model, status=DroneUnit.Status.AVAILABLE)
        .order_by('pk')
        .first()
    )
    if not unit:
        raise RentalDomainError('该型号暂无可租设备。', 409)

    unit.status = DroneUnit.Status.RESERVED
    unit.save(update_fields=['status'])
    days = (end_date - start_date).days + 1
    rent = model.monthly_price * max(days // 30, 1) if days >= 28 else model.daily_price * days
    waive = user.credit_score >= settings.CREDIT_WAIVE_DEPOSIT_SCORE
    values = {
        'user': user,
        'unit': unit,
        'start_date': start_date,
        'end_date': end_date,
        'delivery_type': delivery_type,
        'deposit_paid': Decimal('0') if waive else model.deposit,
        'deposit_waived': waive,
        'insurance_fee': INSURANCE_DAILY * days,
        'rent_amount': rent,
        'credit_score_snapshot': user.credit_score,
        'remark': remark,
    }
    for _ in range(2):
        try:
            with transaction.atomic():
                order = RentalOrder.objects.create(order_no=generate_order_no('RL'), **values)
            break
        except IntegrityError:
            continue
    else:
        raise RentalDomainError('订单号生成冲突，请重试。', 409)
    logger.info(
        'rental_order_created',
        extra={'rental_order_no': order.order_no, 'user_id': user.pk},
    )
    return order


@transaction.atomic
def pay_rental_order(*, order_id, queryset):
    try:
        order = queryset.select_for_update().get(pk=order_id)
    except RentalOrder.DoesNotExist as exc:
        raise RentalDomainError('租赁订单不存在。', 404) from exc
    if order.status != RentalOrder.Status.PENDING_PAY:
        raise RentalDomainError('订单当前状态不可支付。')
    unit = DroneUnit.objects.select_for_update().get(pk=order.unit_id)
    if unit.status != DroneUnit.Status.RESERVED:
        raise RentalDomainError('设备未处于待支付锁定状态。', 409)
    unit.status = DroneUnit.Status.RENTED
    unit.save(update_fields=['status'])
    order.status = RentalOrder.Status.RENTING
    order.save(update_fields=['status'])
    return order


@transaction.atomic
def request_return(*, order_id, queryset):
    try:
        order = queryset.select_for_update().get(pk=order_id)
    except RentalOrder.DoesNotExist as exc:
        raise RentalDomainError('租赁订单不存在。', 404) from exc
    if order.status != RentalOrder.Status.RENTING:
        raise RentalDomainError('当前状态不可申请归还。')
    order.status = RentalOrder.Status.RETURNING
    order.save(update_fields=['status'])
    return order


def parse_damage_fee(value):
    try:
        fee = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise RentalDomainError('damage_fee 格式错误。') from exc
    if fee < 0:
        raise RentalDomainError('damage_fee 不能小于 0。')
    return fee


@transaction.atomic
def inspect_return(*, order_id, damage_fee):
    try:
        order = (
            RentalOrder.objects.select_for_update()
            .select_related('unit')
            .get(pk=order_id)
        )
    except RentalOrder.DoesNotExist as exc:
        raise RentalDomainError('租赁订单不存在。', 404) from exc
    if order.status != RentalOrder.Status.RETURNING:
        raise RentalDomainError('当前订单状态不可验机。')
    unit = DroneUnit.objects.select_for_update().get(pk=order.unit_id)
    refund = max(order.deposit_paid - damage_fee, Decimal('0'))
    order.damage_fee = damage_fee
    order.status = RentalOrder.Status.SETTLED
    order.remark = f'{order.remark or ""} | 验机退押金 {refund}'.strip()
    order.save(update_fields=['damage_fee', 'status', 'remark'])
    if damage_fee:
        unit.depreciation += damage_fee
        unit.status = DroneUnit.Status.MAINTAINING
        MaintenanceRecord.objects.create(
            unit=unit,
            content=f'租赁归还损伤维修，订单 {order.order_no}',
            cost=damage_fee,
        )
    else:
        unit.status = DroneUnit.Status.AVAILABLE
    unit.save(update_fields=['depreciation', 'status'])
    logger.info(
        'rental_return_inspected',
        extra={'rental_order_no': order.order_no, 'damage_fee': damage_fee},
    )
    return order, refund
