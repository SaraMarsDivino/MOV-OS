from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Deduplicate sucursales by nombre in both reports and legacy tables, keeping the oldest row.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show the cleanup plan without changing data.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        from reports.models import Sucursal as ReportSucursal
        from sucursales.models import Sucursal as LegacySucursal
        from auth_app.models import User
        from users.models import Vendedor
        from cashier.models import AperturaCierreCaja, Venta, Devolucion, NotaCredito
        from products.models import Product, StockSucursal, TransferenciaStock, AjusteStock

        report_groups = defaultdict(list)
        for sucursal in ReportSucursal.objects.all().order_by('id'):
            key = (sucursal.nombre or '').strip().casefold()
            report_groups[key].append(sucursal)

        legacy_groups = defaultdict(list)
        for sucursal in LegacySucursal.objects.all().order_by('id'):
            key = (sucursal.nombre or '').strip().casefold()
            legacy_groups[key].append(sucursal)

        report_dupes = {k: v for k, v in report_groups.items() if k and len(v) > 1}
        legacy_dupes = {k: v for k, v in legacy_groups.items() if k and len(v) > 1}

        self.stdout.write(f'Reports duplicates groups: {len(report_dupes)}')
        self.stdout.write(f'Legacy duplicates groups: {len(legacy_dupes)}')

        if dry_run:
            for key, items in report_dupes.items():
                self.stdout.write(f'[REPORTS] {key}: keep {items[0].id}, remove {[s.id for s in items[1:]]}')
            for key, items in legacy_dupes.items():
                self.stdout.write(f'[LEGACY] {key}: keep {items[0].id}, remove {[s.id for s in items[1:]]}')
            return

        with transaction.atomic():
            # Merge report branches first because User permissions depend on them.
            for key, items in report_dupes.items():
                keep = items[0]
                losers = items[1:]
                loser_ids = [s.id for s in losers]
                for user in User.objects.filter(sucursales_autorizadas__in=loser_ids).distinct():
                    current_ids = list(user.sucursales_autorizadas.values_list('id', flat=True))
                    merged_ids = sorted(set([sid for sid in current_ids if sid not in loser_ids] + [keep.id]))
                    user.sucursales_autorizadas.set(merged_ids)
                for loser in losers:
                    loser.delete()
                self.stdout.write(self.style.SUCCESS(f'[REPORTS] kept {keep.id} for {key}, removed {loser_ids}'))

            # Merge legacy branches and reassign foreign keys.
            for key, items in legacy_dupes.items():
                keep = items[0]
                losers = items[1:]
                loser_ids = [s.id for s in losers]

                # Reassign relations from products/cashier models to the canonical branch.
                Product.objects.filter(sucursal_id__in=loser_ids).update(sucursal=keep)
                StockSucursal.objects.filter(sucursal_id__in=loser_ids).update(sucursal=keep)
                TransferenciaStock.objects.filter(origen_id__in=loser_ids).update(origen=keep)
                TransferenciaStock.objects.filter(destino_id__in=loser_ids).update(destino=keep)
                AjusteStock.objects.filter(sucursal_id__in=loser_ids).update(sucursal=keep)
                AperturaCierreCaja.objects.filter(sucursal_id__in=loser_ids).update(sucursal=keep)
                Venta.objects.filter(sucursal_id__in=loser_ids).update(sucursal=keep)
                Devolucion.objects.filter(sucursal_id__in=loser_ids).update(sucursal=keep)
                NotaCredito.objects.filter(sucursal_id__in=loser_ids).update(sucursal=keep)

                vendedor_ids = list(Vendedor.objects.filter(sucursales_autorizadas__in=loser_ids).values_list('id', flat=True).distinct())
                for vendedor in Vendedor.objects.filter(id__in=vendedor_ids):
                    current_ids = list(vendedor.sucursales_autorizadas.values_list('id', flat=True))
                    merged_ids = sorted(set([sid for sid in current_ids if sid not in loser_ids] + [keep.id]))
                    vendedor.sucursales_autorizadas.set(merged_ids)

                for loser in losers:
                    loser.delete()
                self.stdout.write(self.style.SUCCESS(f'[LEGACY] kept {keep.id} for {key}, removed {loser_ids}'))

        self.stdout.write(self.style.SUCCESS('Sucursal deduplication completed.'))
