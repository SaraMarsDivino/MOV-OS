import { useMemo, useState } from 'react';

export type Product = {
  id: number;
  name: string;
  price: number;
  stock: number;
  allowSaleWithoutStock: boolean;
  inSucursal: boolean;
  categoriaId?: number | null;
  categoriaNombre?: string | null;
};

type Props = {
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
  hasSearched: boolean;
  onSearch: () => void;
  products: Product[];
  onAddProduct: (product: Product) => void;
};

export default function CatalogPanel({
  searchQuery,
  onSearchQueryChange,
  hasSearched,
  onSearch,
  products,
  onAddProduct,
}: Props) {
  const showResults = hasSearched;
  const [activeCat, setActiveCat] = useState<number | null | 'all'>('all');

  const categories = useMemo(() => {
    if (!products.length) return [];
    const seen = new Map<number | null, string>();
    let hasUncategorized = false;
    for (const p of products) {
      if (p.categoriaId != null && !seen.has(p.categoriaId)) {
        seen.set(p.categoriaId, p.categoriaNombre || String(p.categoriaId));
      } else if (p.categoriaId == null) {
        hasUncategorized = true;
      }
    }
    const cats: { id: number | null; nombre: string }[] = [];
    seen.forEach((nombre, id) => cats.push({ id, nombre }));
    cats.sort((a, b) => a.nombre.localeCompare(b.nombre));
    if (hasUncategorized) cats.push({ id: null, nombre: 'Sin categoría' });
    return cats;
  }, [products]);

  const filtered = useMemo(() => {
    if (activeCat === 'all') return products;
    return products.filter((p) => p.categoriaId === activeCat);
  }, [products, activeCat]);

  const showCatTabs = showResults && categories.length > 1;

  return (
    <div className="h-full flex flex-col min-h-0 bg-slate-300">
      <div className="p-3 border-b-2 border-slate-400 bg-slate-200">
        <div className="flex items-baseline justify-between gap-2">
          <div className="text-sm font-semibold text-slate-900 normal-case tracking-normal">
            Buscar productos
          </div>
          {showResults ? <div className="text-xs text-slate-500">{filtered.length} resultados</div> : null}
        </div>

        <div className="mt-2 grid grid-cols-1 gap-2">
          <input
            value={searchQuery}
            onChange={(e) => onSearchQueryChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') onSearch();
            }}
            placeholder="Buscar por nombre o código de barras"
            className="w-full rounded-lg bg-white border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500"
          />
          <button
            type="button"
            onClick={onSearch}
            className="min-h-[44px] w-full rounded-lg bg-sky-600 text-white font-black hover:bg-sky-500 active:scale-[0.97] transition-all duration-100"
          >
            Buscar
          </button>
        </div>
      </div>

      {showCatTabs && (
        <div className="flex gap-1 overflow-x-auto px-2 py-2 bg-slate-200 border-b-2 border-slate-400 scrollbar-hide">
          <button
            type="button"
            onClick={() => setActiveCat('all')}
            className={`shrink-0 rounded-lg border-2 border-slate-400 px-3 py-1 text-xs font-black transition-colors ${activeCat === 'all' ? 'bg-slate-800 text-white border-slate-800' : 'bg-white text-slate-700 hover:bg-slate-100'}`}
          >
            Todas
          </button>
          {categories.map((c) => (
            <button
              key={String(c.id)}
              type="button"
              onClick={() => setActiveCat(c.id)}
              className={`shrink-0 rounded-lg border-2 border-slate-400 px-3 py-1 text-xs font-black transition-colors ${activeCat === c.id ? 'bg-slate-800 text-white border-slate-800' : 'bg-white text-slate-700 hover:bg-slate-100'}`}
            >
              {c.nombre}
            </button>
          ))}
        </div>
      )}

      {showResults ? (
        <div className="min-h-0 flex-1 overflow-y-auto bg-slate-300">
          <ul className="divide-y-2 divide-slate-400">
            {filtered.length === 0 ? (
              <li className="p-3 text-sm text-slate-500">No se encontraron productos.</li>
            ) : (
              filtered.map((p) => {
                const disabled = (!p.inSucursal) || (p.stock <= 0 && !p.allowSaleWithoutStock);
                return (
                  <li key={p.id} className="p-3 hover:bg-slate-200 transition-colors duration-100">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-sm font-semibold truncate" title={p.name}>
                          {p.name}
                        </div>
                        <div className="mt-0.5 text-xs text-slate-500 truncate">
                          Stock: {p.stock}
                          {!p.inSucursal ? ' · Otra sucursal' : disabled ? ' · Agotado' : ''}
                          {p.categoriaNombre ? ` · ${p.categoriaNombre}` : ''}
                        </div>
                      </div>

                      <div className="flex items-center gap-3 shrink-0">
                        <div className="text-sm font-extrabold text-emerald-700">
                          ${Math.round(p.price).toLocaleString('es-CL')}
                        </div>
                        <button
                          type="button"
                          onClick={() => onAddProduct(p)}
                          disabled={disabled}
                          className={
                            'min-h-[44px] min-w-[44px] rounded-lg font-black ' +
                            (disabled
                              ? 'bg-slate-200 text-slate-500 cursor-not-allowed'
                              : 'bg-emerald-400 text-slate-950 hover:bg-emerald-300 active:scale-95 transition-all duration-100')
                          }
                          aria-label={`Agregar ${p.name}`}
                        >
                          +
                        </button>
                      </div>
                    </div>
                  </li>
                );
              })
            )}
          </ul>
        </div>
      ) : (
        <div className="min-h-0 flex-1 flex items-center justify-center p-6 text-center bg-slate-300">
          <div>
            <div className="text-sm font-semibold text-slate-700">Busca para ver productos</div>
            <div className="mt-1 text-xs text-slate-500">
              La lista aparece solo después de presionar "Buscar" (o Enter).
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
