import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';

import {
  AdminDashboardPage,
  UsersManagementPage,
  UserEditPage,
  UserCreatePage,
  ProductsManagementPage,
  ReportsDashboardPage,
  SucursalesManagementPage,
  OpenCashPage,
  MarketAnalysisPage,
  SucursalCreatePage,
  SucursalEditPage,
} from './pages';

declare global {
  interface Window {
    __MOVOS_REACT_PAGE__?: string;
  }
}

function AppRouter() {
  const page = window.__MOVOS_REACT_PAGE__ || '';
  if (page === 'admin-dashboard') return <AdminDashboardPage />;
  if (page === 'users-management') return <UsersManagementPage />;
  if (page === 'users-management-edit') return <UserEditPage />;
  if (page === 'users-management-create') return <UserCreatePage />;
  if (page === 'products-management') return <ProductsManagementPage />;
  if (page === 'reports-dashboard') return <ReportsDashboardPage />;
  if (page === 'sucursales-management') return <SucursalesManagementPage />;
  if (page === 'cashier-open-caja') return <OpenCashPage />;
  if (page === 'market-analysis') return <MarketAnalysisPage />;
  if (page === 'sucursal-create') return <SucursalCreatePage />;
  if (page === 'sucursal-edit') return <SucursalEditPage />;

  return (
    <div className="min-h-[calc(100dvh-56px)] bg-slate-200 p-4">
      <div className="mx-auto max-w-3xl rounded-2xl border-2 border-black bg-white p-4 text-sm shadow">
        Página React no configurada: <b>{page || '(vacío)'}</b>
      </div>
    </div>
  );
}

const rootEl = document.getElementById('root');
if (rootEl) {
  ReactDOM.createRoot(rootEl).render(
    <React.StrictMode>
      <AppRouter />
    </React.StrictMode>,
  );
}
