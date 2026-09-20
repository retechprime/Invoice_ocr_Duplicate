import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { createRoot as createReactRoot } from 'react-dom/client';
import './style.css';
import retechPrimeLogo from './retechprime-logo.png';

type Invoice = {
  invoice_id: string;
  filename: string;
  status: string;
  stage?: string;
  processing_time_seconds?: number | null;
  pages?: number;
  uploaded_at?: string;
  completed_at?: string;
  content_type?: string;
  error?: string;
  invoice_number?: string | null;
};

type Stats = {
  total: number;
  queued: number;
  processing: number;
  processing_done: number;
  approved: number;
  edi_processing: number;
  edi_generated: number;
  failed: number;
  average_processing_time_seconds: number;
  average_pages: number;
};

const API = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');

async function api(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers);

  const response = await fetch(`${API}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  const type = response.headers.get('content-type') || '';

  return type.includes('application/json')
    ? response.json()
    : response;
}

function formatTime(seconds: number | null | undefined) {
  if (seconds == null || !Number.isFinite(Number(seconds))) {
    return '—';
  }

  const value = Number(seconds);

  if (value < 60) {
    return `${value.toFixed(1)}s`;
  }

  const minutes = Math.floor(value / 60);
  const remaining = value % 60;

  return `${minutes}m ${remaining.toFixed(0)}s`;
}

function statusLabel(value: string) {
  const labels: Record<string, string> = {
    queued: 'Queued',
    processing: 'Processing',
    processing_done: 'Ready for review',
    approved: 'Approved',
    edi_processing: 'EDI processing',
    edi_generated: 'EDI generated',
    ocr_failed: 'OCR failed',
    extraction_failed: 'Extraction failed',
    edi_failed: 'EDI failed',
  };

  const key = String(value || 'unknown').toLowerCase();
  return labels[key] || key.replace(/_/g, ' ');
}

function StatusBadge({ value }: { value: string }) {
  const cls = String(value || 'unknown')
    .toLowerCase()
    .replace(/_/g, '-');

  return (
    <span className={`status-badge ${cls}`}>
      {statusLabel(value)}
    </span>
  );
}

type IconName =
  | 'file'
  | 'processing'
  | 'user'
  | 'check'
  | 'x'
  | 'clock'
  | 'upload'
  | 'search'
  | 'eye'
  | 'document'
  | 'trash'
  | 'more'
  | 'bell'
  | 'folder';

function Icon({
  name,
  size = 22,
  strokeWidth = 2,
}: {
  name: IconName;
  size?: number;
  strokeWidth?: number;
}) {
  const common = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  };

  const paths: Record<IconName, ReactNode> = {
    file: (
      <>
        <path d="M6 3.5h8l4 4V20.5H6z" />
        <path d="M14 3.5v4h4" />
        <path d="M9 12h6M9 15.5h6" />
      </>
    ),
    processing: (
      <>
        <circle cx="12" cy="12" r="8.5" strokeDasharray="8 5" />
      </>
    ),
    user: (
      <>
        <circle cx="12" cy="8" r="3.5" />
        <path d="M5.5 20c.7-3.2 2.9-5 6.5-5s5.8 1.8 6.5 5" />
      </>
    ),
    check: (
      <path d="m5 12.5 4.2 4.2L19 7" />
    ),
    x: (
      <path d="m7 7 10 10M17 7 7 17" />
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="8.5" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    upload: (
      <>
        <path d="M12 16V5" />
        <path d="m8 9 4-4 4 4" />
        <path d="M5 15.5v2A2.5 2.5 0 0 0 7.5 20h9a2.5 2.5 0 0 0 2.5-2.5v-2" />
      </>
    ),
    search: (
      <>
        <circle cx="10.8" cy="10.8" r="5.8" />
        <path d="m15.3 15.3 4 4" />
      </>
    ),
    eye: (
      <>
        <path d="M2.8 12s3.2-5 9.2-5 9.2 5 9.2 5-3.2 5-9.2 5-9.2-5-9.2-5Z" />
        <circle cx="12" cy="12" r="2.2" />
      </>
    ),
    document: (
      <>
        <path d="M6 3.5h8l4 4V20.5H6z" />
        <path d="M14 3.5v4h4" />
        <path d="M9 12h6M9 15h4" />
      </>
    ),
    trash: (
      <>
        <path d="M5 7h14M9 7V4.5h6V7M7 7l.8 13h8.4L17 7M10 10.5v6M14 10.5v6" />
      </>
    ),
    more: (
      <>
        <circle cx="5" cy="12" r="1" fill="currentColor" stroke="none" />
        <circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" />
        <circle cx="19" cy="12" r="1" fill="currentColor" stroke="none" />
      </>
    ),
    bell: (
      <>
        <path d="M18 9.8c0-3.5-2.2-5.8-6-5.8S6 6.3 6 9.8c0 6-2.2 6-2.2 7.2h16.4C20.2 15.8 18 15.8 18 9.8Z" />
        <path d="M9.5 20h5" />
      </>
    ),
    folder: (
      <path d="M3.5 7.5h6l2 2h9v9.5h-17zM3.5 7.5v-2h5l2 2" />
    ),
  };

  return <svg {...common}>{paths[name]}</svg>;
}

function Metric({
  label,
  value,
  tone = '',
  icon = 'file',
}: {
  label: string;
  value: string | number;
  tone?: string;
  icon?: IconName;
}) {
  return (
    <div className={`metric-card ${tone}`}>
      <div className="metric-icon">
        <Icon name={icon} size={23} strokeWidth={2} />
      </div>
      <div className="metric-copy">
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

function FilePreview({ invoice }: { invoice: Invoice }) {
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let objectUrl = '';
    let cancelled = false;

    async function load() {
      setUrl('');
      setError('');

      try {
        const response = await api(
          `/invoices/${encodeURIComponent(invoice.invoice_id)}/file`
        );

        const blob =
          response instanceof Response
            ? await response.blob()
            : new Blob([response]);

        if (!blob.size) {
          throw new Error('Empty document response');
        }

        objectUrl = URL.createObjectURL(blob);

        if (!cancelled) {
          setUrl(objectUrl);
        }
      } catch (e) {
        if (!cancelled) {
          setError(
            e instanceof Error
              ? e.message
              : 'Preview unavailable'
          );
        }
      }
    }

    load();

    return () => {
      cancelled = true;

      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [invoice.invoice_id]);

  if (error) {
    return (
      <div className="preview-state">
        {error}
      </div>
    );
  }

  if (!url) {
    return (
      <div className="preview-state">
        Loading document…
      </div>
    );
  }

  const pdf =
    invoice.content_type?.includes('pdf') ||
    /\.pdf$/i.test(invoice.filename);

  if (pdf) {
    return (
      <iframe
        title={invoice.filename}
        src={url}
      />
    );
  }

  return (
    <img
      src={url}
      alt={invoice.filename}
    />
  );
}

function humanizeKey(key: string) {
  return String(key || '')
    .replace(/[_-]+/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\b\w/g, c => c.toUpperCase());
}

function getReviewData(payload: any) {
  const reviewed = payload?.review?.reviewed_data;
  if (reviewed && typeof reviewed === 'object') {
    return reviewed;
  }

  const source =
    payload?.result ??
    payload?.invoice ??
    payload?.extraction ??
    payload ??
    {};

  const extraction = source?.extraction ?? source;
  return extraction && typeof extraction === 'object' ? extraction : {};
}

function firstValue(obj: any, keys: string[]) {
  for (const key of keys) {
    const value = obj?.[key];
    if (value !== undefined && value !== null && value !== '') return value;
  }
  return '';
}

function ReviewField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: any;
  onChange: (value: string) => void;
}) {
  const display = Array.isArray(value)
    ? value.join(', ')
    : typeof value === 'object' && value !== null
      ? JSON.stringify(value)
      : String(value ?? '');

  return (
    <div className="review-field">
      <label>{label}</label>

      <input
        value={display}
        onChange={e => onChange(e.target.value)}
        placeholder="Not detected"
      />

    </div>
  );
}

function Review({
  invoice,
  onBack,
  onDelete,
}: {
  invoice: Invoice;
  onBack: () => void;
  onDelete: () => void;
}) {
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');
  const [values, setValues] = useState<Record<string, string>>({});
  const [reviewedData, setReviewedData] = useState<any>(null);
  const [allVerified, setAllVerified] = useState(false);
  const [approving, setApproving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    let cancelled = false;

    api(`/invoices/${encodeURIComponent(invoice.invoice_id)}/review`)
      .then(data => {
        if (cancelled) return;

        setResult(data);

        const extraction = getReviewData(data);
        setReviewedData(
          data?.review?.reviewed_data ??
          extraction
        );
        const initial: Record<string, string> = {};

        const scalarValue = (value: any): string => {
          if (value === undefined || value === null) return '';

          // Support extraction responses such as:
          // { value: "12345", page: 1, confidence: 0.98 }
          if (
            typeof value === 'object' &&
            !Array.isArray(value) &&
            Object.prototype.hasOwnProperty.call(value, 'value')
          ) {
            return scalarValue(value.value);
          }

          if (Array.isArray(value)) {
            return value.map(v => scalarValue(v)).join(', ');
          }

          if (typeof value === 'object') {
            return JSON.stringify(value);
          }

          return String(value);
        };

        const walk = (obj: any, prefix = '') => {
          if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return;

          Object.entries(obj).forEach(([key, value]) => {
            // Technical extraction metadata is not shown as an editable field.
            if (
              ['page', 'pages', 'confidence', 'bbox', 'bounding_box', 'source',
                'method', 'raw_text', 'text', 'coordinates'].includes(key.toLowerCase())
            ) {
              return;
            }

            const path = prefix ? `${prefix}.${key}` : key;

            if (
              value &&
              typeof value === 'object' &&
              !Array.isArray(value) &&
              !Object.prototype.hasOwnProperty.call(value, 'value')
            ) {
              walk(value, path);
            } else if (!Array.isArray(value) || value.length > 0) {
              initial[path] = scalarValue(value);
            }
          });
        };

        walk(extraction);
        setValues(initial);
      })
      .catch(e => {
        if (!cancelled) {
          setError(
            e instanceof Error ? e.message : 'Unable to load invoice'
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [invoice.invoice_id]);

  const data = getReviewData(result);

  const scalarValue = (value: any): string => {
    if (value === undefined || value === null) return '';

    if (
      typeof value === 'object' &&
      !Array.isArray(value) &&
      Object.prototype.hasOwnProperty.call(value, 'value')
    ) {
      return scalarValue(value.value);
    }

    if (Array.isArray(value)) {
      return value.map(v => scalarValue(v)).join(', ');
    }

    if (typeof value === 'object') {
      return JSON.stringify(value);
    }

    return String(value);
  };

  const isTechnicalKey = (key: string) =>
    [
      'page',
      'pages',
      'confidence',
      'bbox',
      'bounding_box',
      'source',
      'method',
      'raw_text',
      'text',
      'coordinates',
    ].includes(key.toLowerCase());

  const isLineItemsKey = (key: string) =>
    ['line_items', 'items', 'item_details', 'lineitems'].includes(
      key.toLowerCase()
    );

  const isTotalsKey = (key: string) =>
    ['totals', 'total', 'summary'].includes(key.toLowerCase());

  const isOtherInformationKey = (key: string) =>
    ['other_information', 'other_info', 'additional_information'].includes(
      key.toLowerCase()
    );

  type DisplayField = {
    key: string;
    label: string;
    value: string;
  };

  const collectFields = (
    obj: any,
    prefix = ''
  ): DisplayField[] => {
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return [];

    const output: DisplayField[] = [];

    Object.entries(obj).forEach(([key, rawValue]) => {
      if (isTechnicalKey(key)) return;

      const path = prefix ? `${prefix}.${key}` : key;
      if (
        rawValue &&
        typeof rawValue === 'object' &&
        !Array.isArray(rawValue) &&
        Object.prototype.hasOwnProperty.call(rawValue, 'value')
      ) {
        output.push({
          key: path,
          label: humanizeKey(key),
          value: scalarValue(rawValue),
        });
        return;
      }

      if (
        rawValue &&
        typeof rawValue === 'object' &&
        !Array.isArray(rawValue)
      ) {
        output.push(...collectFields(rawValue, path));
        return;
      }

      if (Array.isArray(rawValue)) {
        // Arrays such as line_items are rendered separately.
        if (isLineItemsKey(key)) return;

        if (rawValue.length > 0) {
          output.push({
            key: path,
            label: humanizeKey(key),
            value: scalarValue(rawValue),
          });
        }
        return;
      }

      output.push({
        key: path,
        label: humanizeKey(key),
        value: scalarValue(rawValue),
      });
    });

    return output;
  };

  const setNestedValue = (source: any, path: string, value: string) => {
    const output = structuredClone(source ?? {});
    const parts = path.split('.');

    let cursor = output;

    for (let i = 0; i < parts.length - 1; i += 1) {
      const raw = parts[i];
      const next = parts[i + 1];
      const key: string | number = /^\d+$/.test(raw) ? Number(raw) : raw;

      if (cursor[key] == null) {
        cursor[key] = /^\d+$/.test(next) ? [] : {};
      }

      cursor = cursor[key];
    }

    const last = parts[parts.length - 1];
    cursor[/^\d+$/.test(last) ? Number(last) : last] = value;

    return output;
  };

  const updateValue = (key: string, value: string) => {
    setValues(prev => ({ ...prev, [key]: value }));
    setReviewedData((prev: any) => setNestedValue(prev, key, value));
    setAllVerified(false);
    setHasChanges(true);
  };

  const isReapproval =
    invoice.status === 'edi_generated' || invoice.status === 'edi_failed';


  const approve = async () => {
    if (!reviewedData || approving) return;

    if (invoice.status === 'edi_generated' && !hasChanges) {
      setError('Change at least one field before re-approving a generated EDI.');
      return;
    }

    setApproving(true);
    setError('');

    try {
      await api(
        `/invoices/${encodeURIComponent(invoice.invoice_id)}/review`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            reviewed_data: reviewedData,
          }),
        }
      );

      await api(
        `/invoices/${encodeURIComponent(invoice.invoice_id)}/approve`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({}),
        }
      );

      onBack();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Approval failed'
      );
    } finally {
      setApproving(false);
    }
  };


  const extractionObject =
    data && typeof data === 'object' ? data : {};

  const lineItemsKey = Object.keys(extractionObject).find(isLineItemsKey);

  const items = lineItemsKey &&
    Array.isArray(extractionObject[lineItemsKey])
    ? extractionObject[lineItemsKey]
    : [];

  const topLevelFields: DisplayField[] = [];

  Object.entries(extractionObject).forEach(([key, value]) => {
    if (
      isTechnicalKey(key) ||
      isLineItemsKey(key) ||
      isTotalsKey(key) ||
      isOtherInformationKey(key) ||
      key.toLowerCase() === 'extraction_notes'
    ) {
      return;
    }

    if (
      value &&
      typeof value === 'object' &&
      !Array.isArray(value) &&
      !Object.prototype.hasOwnProperty.call(value, 'value')
    ) {
      topLevelFields.push(...collectFields(value, key));
    } else {
      topLevelFields.push({
        key,
        label: humanizeKey(key),
        value: scalarValue(value),
      });
    }
  });

  const totalsFields: DisplayField[] = [];
  const totalsKey = Object.keys(extractionObject).find(isTotalsKey);

  if (totalsKey) {
    const totalsValue = extractionObject[totalsKey];

    if (
      totalsValue &&
      typeof totalsValue === 'object' &&
      !Array.isArray(totalsValue)
    ) {
      totalsFields.push(...collectFields(totalsValue, totalsKey));
    } else {
      totalsFields.push({
        key: totalsKey,
        label: humanizeKey(totalsKey),
        value: scalarValue(totalsValue),
      });
    }
  }

  const otherFields: DisplayField[] = [];
  const otherKey = Object.keys(extractionObject).find(
    isOtherInformationKey
  );

  if (otherKey) {
    const otherValue = extractionObject[otherKey];

    if (
      otherValue &&
      typeof otherValue === 'object' &&
      !Array.isArray(otherValue)
    ) {
      otherFields.push(...collectFields(otherValue, otherKey));
    } else {
      otherFields.push({
        key: otherKey,
        label: humanizeKey(otherKey),
        value: scalarValue(otherValue),
      });
    }
  }

  const getItemFields = (
    item: any,
    index: number
  ): DisplayField[] => {
    if (!item || typeof item !== 'object') {
      return [
        {
          key: `item_${index}`,
          label: `Item ${index + 1}`,
          value: scalarValue(item),
        },
      ];
    }

    return collectFields(item, `item_${index}`);
  };

  const itemFieldGroups = items.map(
    (item: any, index: number) => getItemFields(item, index)
  );

  const allFields = [
    ...topLevelFields,
    ...totalsFields,
    ...otherFields,
    ...itemFieldGroups.flat(),
  ];

  const canApprove =
    allFields.length > 0 &&
    allVerified &&
    (
      invoice.status === 'processing_done' ||
      invoice.status === 'edi_failed' ||
      (invoice.status === 'edi_generated' && hasChanges)
    );

  const renderFields = (fields: DisplayField[]) => {
    if (!fields.length) {
      return (
        <div className="empty-review">
          No information was returned.
        </div>
      );
    }

    return (
      <div className="review-fields">
        {fields.map(field => (
          <ReviewField
            key={field.key}
            label={field.label}
            value={values[field.key] ?? field.value}
            onChange={value => updateValue(field.key, value)}
          />
        ))}
      </div>
    );
  };

  return (
    <div className="review-shell">
      <header className="review-header">
        <button className="button secondary review-back" onClick={onBack}>
          <span className="back-arrow">←</span>
          <span>Invoices</span>
        </button>

        <div className="review-title">
          <div className="review-kicker">
            <span className="eyebrow">INVOICE REVIEW</span>
            <span className="review-divider">/</span>
            <span className="review-context">Verification workspace</span>
          </div>

          <h1>{invoice.filename}</h1>

          <div className="review-meta">
            <StatusBadge value={invoice.status} />
            <span className="review-time">
              Compare the extracted information with the original document.
            </span>
          </div>
        </div>

        <button className="button danger review-delete" onClick={onDelete}>
          Delete invoice
        </button>
      </header>

      {error && <div className="alert error">{error}</div>}

      {isReapproval && (
        <div className="alert">
          {invoice.status === 'edi_failed'
            ? 'EDI generation failed. Correct the fields if needed, verify them again, and re-approve to retry EDI generation.'
            : 'EDI 801 has already been generated. If you change any value, verify the fields again and re-approve to regenerate the EDI.'}
        </div>
      )}


      <div className="review-workspace">
        <section className="panel preview-panel">
          <div className="document-panel-head">
            <div>
              <span className="eyebrow">SOURCE DOCUMENT</span>
              <h2>Original Invoice</h2>
            </div>
            <span className="document-reference">Reference document</span>
          </div>

          <div className="document-preview">
            <FilePreview invoice={invoice} />
          </div>
        </section>

        <section className="panel extraction-panel">
          <div className="extraction-scroll">
            <div className="extraction-head">
              <div>
                <span className="eyebrow">EXTRACTED INFORMATION</span>
                <h2>Invoice details</h2>
              </div>
              <span className="edit-hint">Fields can be edited before approval</span>
            </div>

            <div className="review-section">
              <div className="review-section-title"><span>Invoice Information</span></div>
              {renderFields(topLevelFields)}
            </div>

            {items.length > 0 && (
              <div className="review-section">
                <div className="review-section-title"><span>Item Details</span></div>

                {itemFieldGroups.map(
                  (fields: DisplayField[], index: number) => (
                    <div className="item-card" key={index}>
                      <div className="item-card-title">
                        Item {index + 1}
                      </div>
                      {renderFields(fields)}
                    </div>
                  )
                )}
              </div>
            )}

            {totalsFields.length > 0 && (
              <div className="review-section">
                <div className="review-section-title"><span>Totals</span></div>
                {renderFields(totalsFields)}
              </div>
            )}

            {otherFields.length > 0 && (
              <div className="review-section">
                <div className="review-section-title"><span>Other Information</span></div>
                {renderFields(otherFields)}
              </div>
            )}

            {allFields.length === 0 && !error && (
              <div className="empty-review">
                No extracted information is available yet.
              </div>
            )}
          </div>

          <div className="review-footer">
            <label className="final-check">
              <input
                type="checkbox"
                checked={allVerified}
                onChange={e => setAllVerified(e.target.checked)}
                aria-label="Confirm that all extracted values were checked"
              />
              <span>
                I have checked all extracted values against the original
                invoice.
              </span>
            </label>

            <button
              className="button primary approve-button"
              disabled={!canApprove || approving}
              onClick={approve}
            >
              {approving
                ? 'Approving…'
                : isReapproval
                  ? 'Re-approve & Regenerate EDI'
                  : 'Approve'}
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}

function Dashboard() {
  const [docs, setDocs] = useState<Invoice[]>([]);
  const [stats, setStats] = useState<Stats>({
    total: 0,
    queued: 0,
    processing: 0,
    processing_done: 0,
    approved: 0,
    edi_processing: 0,
    edi_generated: 0,
    failed: 0,
    average_processing_time_seconds: 0,
    average_pages: 0,
  });

  const [file, setFile] = useState<File | null>(null);
  const [selected, setSelected] = useState<Invoice | null>(null);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Invoice | null>(null);
  const [now, setNow] = useState(Date.now());

  const inputRef = useRef<HTMLInputElement>(null);

  async function load() {
    try {
      const params = new URLSearchParams({
        page: '1',
        page_size: '100',
      });

      if (search.trim()) params.set('search', search.trim());
      if (status) params.set('status', status);

      const [list, summary] = await Promise.all([
        api(`/invoices?${params}`),
        api('/invoices/stats/summary'),
      ]);

      setDocs(list.items || list.documents || []);
      setStats({
        total: Number(summary.total || 0),
        queued: Number(summary.queued || 0),
        processing: Number(summary.processing || 0),
        processing_done: Number(summary.processing_done || 0),
        approved: Number(summary.approved || 0),
        edi_processing: Number(summary.edi_processing || 0),
        edi_generated: Number(summary.edi_generated || 0),
        failed: Number(summary.failed || 0),
        average_processing_time_seconds: Number(
          summary.average_processing_time_seconds || 0
        ),
        average_pages: Number(summary.average_pages || 0),
      });

      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to reach API');
    }
  }

  useEffect(() => {
    load();
  }, [search, status]);

  useEffect(() => {
    const timer = setInterval(() => {
      load();
      setNow(Date.now());
    }, 2000);

    return () => clearInterval(timer);
  }, [search, status]);

  async function upload(nextFile: File | null = file) {
    if (!nextFile) {
      setError('Choose an invoice first.');
      return;
    }

    setBusy(true);
    setError('');
    setMessage('');
    setFile(nextFile);

    try {
      const form = new FormData();
      form.append('file', nextFile);

      const result = await api('/invoices/upload', {
        method: 'POST',
        body: form,
      });

      setMessage(`Invoice accepted: ${result.filename || result.invoice_id}`);
      setFile(null);

      if (inputRef.current) inputRef.current.value = '';
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setBusy(false);
    }
  }

  function choose(next: File | null) {
    if (!next) return;

    if (!/\.(pdf|jpg|jpeg|png|bmp|webp|tif|tiff)$/i.test(next.name)) {
      setError('Use PDF, JPG, JPEG, PNG, BMP, WEBP or TIFF.');
      return;
    }

    setError('');
    void upload(next);
  }

  async function openInvoice(invoice: Invoice) {
    try {
      setBusy(true);
      const latest = await api(
        `/invoices/${encodeURIComponent(invoice.invoice_id)}/status`
      );
      setSelected({ ...invoice, ...latest });
    } catch {
      setSelected(invoice);
    } finally {
      setBusy(false);
    }
  }

  async function downloadEdi(invoice: Invoice) {
    try {
      setBusy(true);
      setError('');

      const response = await api(
        `/invoices/${encodeURIComponent(invoice.invoice_id)}/edi/download-fixed`
      );

      const blob =
        response instanceof Response
          ? await response.blob()
          : new Blob([response], { type: 'text/plain' });

      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${invoice.invoice_id}_EDI801.txt`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);

      setMessage(`EDI 801 downloaded for ${invoice.filename}.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'EDI download failed');
    } finally {
      setBusy(false);
    }
  }

  async function deleteInvoice(invoice: Invoice) {
    setBusy(true);
    setError('');

    try {
      await api(`/invoices/${encodeURIComponent(invoice.invoice_id)}`, {
        method: 'DELETE',
      });

      setDeleteTarget(null);
      setMessage(`${invoice.filename} deleted.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed');
    } finally {
      setBusy(false);
    }
  }

  function elapsed(invoice: Invoice) {
    if (invoice.processing_time_seconds != null) {
      return formatTime(invoice.processing_time_seconds);
    }

    if (!invoice.uploaded_at) return '—';

    const seconds = Math.max(
      0,
      (now - new Date(invoice.uploaded_at).getTime()) / 1000
    );

    return formatTime(seconds);
  }

  if (selected) {
    return (
      <Review
        invoice={selected}
        onBack={() => {
          setSelected(null);
          load();
        }}
        onDelete={() => setDeleteTarget(selected)}
      />
    );
  }

  return (
    <div className="dashboard-shell">
      <main className="dashboard-content">
        <header className="dashboard-header">
          <div className="dashboard-brand">
            <img
              className="dashboard-logo-image"
              src={retechPrimeLogo}
              alt="ReTechPrime"
            />
          </div>

          <div className="dashboard-header-actions">
            <div className="dashboard-live">
              <span />
              Live
            </div>
          </div>
        </header>

        <section className="dashboard-title">
          <span className="dashboard-eyebrow">INVOICE AI</span>
          <h1>Invoice Processing</h1>
          <p>Upload, process and generate EDI.</p>
        </section>

        {error && <div className="alert error">{error}</div>}

        {message && (
          <div className="download-toast">
            <div className="download-toast-icon">
              ✓
            </div>

            <div className="download-toast-content">
              <div className="download-toast-title">
                EDI 801 Downloaded
              </div>

              <div className="download-toast-text">
                {message}
              </div>
            </div>

            <button
              className="download-toast-close"
              onClick={() => setMessage("")}
              aria-label="Close"
            >
              ×
            </button>
          </div>
        )}

        <section className="dashboard-metrics">
          <Metric label="Total Invoices" value={stats.total} icon="file" />
          <Metric label="Processing" value={stats.processing} tone="blue" icon="processing" />
          <Metric label="Human Review" value={stats.processing_done} tone="amber" icon="user" />
          <Metric label="Approved" value={stats.approved} tone="green" icon="check" />
          <Metric label="Failed" value={stats.failed} tone="red" icon="x" />
          <div className="metric-divider" aria-hidden="true" />
          <Metric
            label="Avg. time"
            value={formatTime(stats.average_processing_time_seconds)}
            tone="blue"
            icon="clock"
          />
          <Metric
            label="Avg. pages"
            value={stats.average_pages.toFixed(1)}
            tone="blue"
            icon="file"
          />
        </section>

        <section className="dashboard-upload">
          <div
            className={`dashboard-dropzone ${file ? 'has-file' : ''}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={e => e.preventDefault()}
            onDrop={e => {
              e.preventDefault();
              choose(e.dataTransfer.files?.[0] || null);
            }}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.jpg,.jpeg,.png,.bmp,.webp,.tif,.tiff"
              onChange={e => choose(e.target.files?.[0] || null)}
            />

            <div className="dashboard-upload-icon">
              <Icon name="upload" size={35} strokeWidth={1.9} />
            </div>

            <div className="dashboard-upload-copy">
              <strong>Upload Invoice</strong>
              <span>
                {file
                  ? file.name
                  : 'Drag & drop PDF, JPG, JPEG or PNG here, or click to browse.'}
              </span>
            </div>

            <button
              type="button"
              className="dashboard-browse"
              disabled={busy}
              onClick={e => {
                e.stopPropagation();
                inputRef.current?.click();
              }}
            >
              <Icon name="folder" size={22} strokeWidth={1.8} />
              <span>{busy ? 'Uploading…' : 'Browse files'}</span>
            </button>
          </div>
        </section>

        <section className="dashboard-invoices">
          <div className="invoice-toolbar">
            <h2>Invoices ({docs.length})</h2>

            <div className="invoice-filters">
              <label className="search-box">
                <Icon name="search" size={21} strokeWidth={1.8} />
                <input
                  placeholder="Search invoice name..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                />
              </label>

              <select value={status} onChange={e => setStatus(e.target.value)}>
                <option value="">All statuses</option>
                <option value="queued">Queued</option>
                <option value="processing">Processing</option>
                <option value="processing_done">Ready for review</option>
                <option value="approved">Approved</option>
                <option value="edi_processing">EDI processing</option>
                <option value="edi_generated">EDI generated</option>
                <option value="ocr_failed">OCR failed</option>
                <option value="extraction_failed">Extraction failed</option>
                <option value="edi_failed">EDI failed</option>
              </select>
            </div>
          </div>

          <div className="invoice-table-wrap">
            <table className="invoice-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Invoice name</th>
                  <th>Status</th>
                  <th>Total time</th>
                  <th>Actions</th>
                  <th aria-hidden="true" />
                </tr>
              </thead>

              <tbody>
                {docs.length ? (
                  docs.map((doc, index) => (
                    <tr key={doc.invoice_id}>
                      <td className="invoice-number">{index + 1}</td>
                      <td>
                        <strong className="invoice-filename">{doc.filename}</strong>
                      </td>
                      <td>
                        <StatusBadge value={doc.status} />
                      </td>
                      <td className="invoice-time">{elapsed(doc)}</td>
                      <td>
                        <div className="invoice-actions">
                          <button
                            className="action-link open"
                            onClick={() => openInvoice(doc)}
                          >
                            <Icon name="eye" size={20} strokeWidth={1.9} />
                            <span>Open</span>
                          </button>

                          {doc.status === 'edi_generated' && (
                            <button
                              className="action-link edi"
                              onClick={() => downloadEdi(doc)}
                            >
                              <Icon name="document" size={20} strokeWidth={1.8} />
                              <span>Download EDI</span>
                            </button>
                          )}

                          <button
                            className="action-link delete"
                            onClick={() => setDeleteTarget(doc)}
                          >
                            <Icon name="trash" size={20} strokeWidth={1.8} />
                            <span>Delete</span>
                          </button>
                        </div>
                      </td>
                      <td>
                        <button className="more-button" aria-label={`More actions for ${doc.filename}`}>
                          <Icon name="more" size={22} strokeWidth={2} />
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="empty">
                      No invoices found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <footer className="dashboard-footer">
          <span>© 2026 <strong>retech prime.</strong> All rights reserved.</span>
          <span>Invoice AI <i /> Faster Processing. Smarter Business.</span>
        </footer>
      </main>

      {deleteTarget && (
        <div className="modal-backdrop">
          <div className="modal">
            <h2>Delete invoice?</h2>
            <p>
              This will permanently remove <strong>{deleteTarget.filename}</strong>{' '}
              and its processing data.
            </p>

            <div className="modal-actions">
              <button
                className="button secondary"
                disabled={busy}
                onClick={() => setDeleteTarget(null)}
              >
                Cancel
              </button>
              <button
                className="button danger"
                disabled={busy}
                onClick={() => deleteInvoice(deleteTarget)}
              >
                {busy ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


function App() {
  return <Dashboard />;
}

createRoot(
  document.getElementById('root')!
).render(
  <App />
);

function createRoot(arg0: HTMLElement) {
  return createReactRoot(arg0);
}

