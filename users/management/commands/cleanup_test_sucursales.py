from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Remove test sucursales created by test flows (names starting with PruebaRep/PruebaSuc).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without changing data.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        from reports.models import Sucursal as ReportSucursal
        from sucursales.models import Sucursal as LegacySucursal
        from auth_app.models import User
        from users.models import Vendedor
        from cashier.models import AperturaCierreCaja, Venta, Devolucion, NotaCredito
        from products.models import Product, StockSucursal, TransferenciaStock, AjusteStock

        report_qs = ReportSucursal.objects.filter(nombre__startswith='PruebaRep')
        legacy_qs = LegacySucursal.objects.filter(nombre__startswith='PruebaSuc')

        report_ids = list(report_qs.values_list('id', flat=True))
        legacy_ids = list(legacy_qs.values_list('id', flat=True))

        self.stdout.write(f'Report sucursales to remove: {report_ids}')
        self.stdout.write(f'Legacy sucursales to remove: {legacy_ids}')

        if dry_run:
            return

        with transaction.atomic():
            if report_ids:
                for user in User.objects.filter(sucursales_autorizadas__in=report_ids).distinct():
                    remaining = [sid for sid in user.sucursales_autorizadas.values_list('id', flat=True) if sid not in report_ids]
                    user.sucursales_autorizadas.set(remaining)
                report_qs.delete()

            if legacy_ids:
                Product.objects.filter(sucursal_id__in=legacy_ids).update(sucursal=None)
                StockSucursal.objects.filter(sucursal_id__in=legacy_ids).delete()
                TransferenciaStock.objects.filter(origen_id__in=legacy_ids).delete()
                TransferenciaStock.objects.filter(destino_id__in=legacy_ids).delete()
                AjusteStock.objects.filter(sucursal_id__in=legacy_ids).delete()
                AperturaCierreCaja.objects.filter(sucursal_id__in=legacy_ids).delete()
                Venta.objects.filter(sucursal_id__in=legacy_ids).delete()
                Devolucion.objects.filter(sucursal_id__in=legacy_ids).delete()
                NotaCredito.objects.filter(sucursal_id__in=legacy_ids).delete()

                for vendedor in Vendedor.objects.filter(sucursales_autorizadas__in=legacy_ids).distinct():
                    remaining = [sid for sid in vendedor.sucursales_autorizadas.values_list('id', flat=True) if sid not in legacy_ids]
                    vendedor.sucursales_autorizadas.set(remaining)

                legacy_qs.delete()

        self.stdout.write(self.style.SUCCESS('Test sucursales cleanup completed.'))
