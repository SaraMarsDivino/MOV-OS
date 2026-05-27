import { formatCLP } from './utils';

type Props = {
  total: number;
  isOpen: boolean;
  onOpen: () => void;
};

export default function MobileBottomBar({ total, isOpen, onOpen }: Props) {
  return (
    <div className="md:hidden">
      <div className="fixed bottom-0 left-0 right-0 z-50 border-t border-slate-200 bg-slate-50/90 backdrop-blur">
        <div className="px-3 py-3 flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={onOpen}
            disabled={isOpen}
            className="min-h-[60px] px-4 rounded-lg bg-emerald-400 text-slate-950 font-black"
          >
            Ver carrito / Pagar
          </button>
        </div>
      </div>

      {/* Spacer so catalog bottom isn't hidden behind the bar */}
      <div className="h-[84px]" />
    </div>
  );
}
