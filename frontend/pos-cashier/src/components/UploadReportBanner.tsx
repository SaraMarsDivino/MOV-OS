import React, { useState } from 'react';

type UploadReport = {
  rows_total?: number;
  distinct_product_codes?: number;
  created?: number;
  updated?: number;
  unchanged?: number;
  duplicates?: Array<any>;
  warnings?: string[];
  errors?: string[];
  created_codes?: string[];
  updated_codes?: string[];
  unchanged_codes?: string[];
};

export default function UploadReportBanner() {
  const report = (window as any).__UPLOAD_REPORT__ as UploadReport | undefined;
  const [show, setShow] = useState(!!report);
  const [expanded, setExpanded] = useState(false);
  if (!report || !show) return null;

  return (
    <div className="bg-white border rounded p-3 mb-4 shadow-sm">
      <div className="flex justify-between items-center">
        <div>
          <strong>Resultados de la carga:</strong>
          <div className="text-sm">{report.rows_total} filas procesadas — {report.distinct_product_codes} productos distintos</div>
        </div>
        <div>
          <button className="btn btn-secondary btn-sm" onClick={() => setShow(false)}>{expanded ? 'Ocultar' : 'Mostrar'}</button>
        </div>
      </div>
      {expanded && (
        <div className="mt-3 text-sm">
          <div>Creados: {report.created}</div>
          <div>Actualizados: {report.updated}</div>
          <div>No cambiados: {report.unchanged}</div>
          <div>Duplicados encontrados: {report.duplicates || 0}</div>
          {report.failures && report.failures.length > 0 && (
            <div className="mt-2 text-danger">
              <strong>Filas fallidas:</strong>
              <ul>
                {report.failures.map((f: any, idx: number) => <li key={idx}>{f.row}: {f.reason}</li>)}
              </ul>
            </div>
          )}
          {report.errors && report.errors.length > 0 && (
            <div className="mt-2 text-danger">
              <strong>Errores:</strong>
              <ul>
                {report.errors.map((e: any, idx: number) => <li key={idx}>{e}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
