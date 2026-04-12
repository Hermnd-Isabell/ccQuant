import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getUnderlyings,
  getExpiryDates,
  getFilteredStats,
  getOptionBars,
  getDailyBars,
  getMergedBars,
  uploadDataFile,
  deleteOptionBars,
  deleteDailyBars,
} from '../api';
import type {
  UnderlyingInfo,
  OptionBarRow,
  DailyBarRow,
  MergedBarRow,
  FilteredStats,
  Granularity,
} from '../types';

type ViewMode = 'option_bars' | 'daily_bars' | 'merged_bars';

export default function DatabasePage() {
  // Underlyings & expiries
  const [underlyings, setUnderlyings] = useState<UnderlyingInfo[]>([]);
  const [selectedUnderlying, setSelectedUnderlying] = useState('');
  const [expiries, setExpiries] = useState<string[]>([]);
  const [selectedExpiry, setSelectedExpiry] = useState('');

  // Filters
  const [viewMode, setViewMode] = useState<ViewMode>('option_bars');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [searchSymbol, setSearchSymbol] = useState('');
  const [granularity, setGranularity] = useState<Granularity>('daily');

  // Stats (filtered)
  const [stats, setStats] = useState<FilteredStats | null>(null);

  // Table
  const [optionRows, setOptionRows] = useState<OptionBarRow[]>([]);
  const [dailyRows, setDailyRows] = useState<DailyBarRow[]>([]);
  const [mergedRows, setMergedRows] = useState<MergedBarRow[]>([]);
  const [tablePage, setTablePage] = useState(1);
  const [tableTotal, setTableTotal] = useState(0);
  const [tableLoading, setTableLoading] = useState(false);
  const PAGE_SIZE = 200;

  // Upload
  const [showUpload, setShowUpload] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadType, setUploadType] = useState<'option' | 'underlying'>('option');
  const [uploadSymbol, setUploadSymbol] = useState('510050');
  const [uploadGranularity, setUploadGranularity] = useState<Granularity>('daily');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [dragover, setDragover] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Delete confirm
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Loading
  const [initLoading, setInitLoading] = useState(true);

  // Cross-hair hover state
  const [hoverCell, setHoverCell] = useState<{ row: number; col: number } | null>(null);

  // ========== Init ==========
  useEffect(() => {
    getUnderlyings()
      .then((unds) => {
        setUnderlyings(unds);
        if (unds.length > 0) setSelectedUnderlying(unds[0].symbol);
      })
      .catch(() => {})
      .finally(() => setInitLoading(false));
  }, []);

  // Load expiries when underlying changes
  useEffect(() => {
    if (!selectedUnderlying) return;
    getExpiryDates(selectedUnderlying)
      .then((dates) => {
        setExpiries(dates);
        setSelectedExpiry(''); // reset
      })
      .catch(() => setExpiries([]));
  }, [selectedUnderlying]);

  // ========== Build filter params ==========
  const filterParams = useCallback(() => {
    const p: Record<string, string> = { underlying: selectedUnderlying };
    if (selectedExpiry) p.expiry = selectedExpiry;
    if (startDate) p.start_date = startDate;
    if (endDate) p.end_date = endDate;
    if (searchSymbol.trim()) p.search = searchSymbol.trim();
    return p;
  }, [selectedUnderlying, selectedExpiry, startDate, endDate, searchSymbol]);

  // ========== Load stats (filtered) ==========
  useEffect(() => {
    if (!selectedUnderlying) return;
    if (granularity === 'minute') {
      setStats({ optionContractCount: 0, optionBarCount: 0, dailyBarCount: 0, dateRange: null });
      return;
    }
    getFilteredStats(filterParams()).then(setStats).catch(() => {});
  }, [selectedUnderlying, selectedExpiry, startDate, endDate, searchSymbol, granularity, filterParams]);

  // ========== Load table data ==========
  const loadTableData = useCallback(async () => {
    if (!selectedUnderlying) return;

    // 分钟级别暂无数据，直接清空
    if (granularity === 'minute') {
      setOptionRows([]);
      setDailyRows([]);
      setMergedRows([]);
      setTableTotal(0);
      return;
    }

    setTableLoading(true);
    try {
      if (viewMode === 'option_bars') {
        const result = await getOptionBars({
          ...filterParams(),
          page: tablePage,
          page_size: PAGE_SIZE,
        });
        setOptionRows(result.data);
        setTableTotal(result.total);
      } else if (viewMode === 'daily_bars') {
        const result = await getDailyBars({
          symbol: selectedUnderlying,
          page: tablePage,
          page_size: PAGE_SIZE,
          start_date: startDate || undefined,
          end_date: endDate || undefined,
        });
        setDailyRows(result.data);
        setTableTotal(result.total);
      } else {
        // merged_bars
        const result = await getMergedBars({
          ...filterParams(),
          page: tablePage,
          page_size: PAGE_SIZE,
        });
        setMergedRows(result.data);
        setTableTotal(result.total);
      }
    } catch {
      setOptionRows([]);
      setDailyRows([]);
      setMergedRows([]);
      setTableTotal(0);
    } finally {
      setTableLoading(false);
    }
  }, [selectedUnderlying, viewMode, tablePage, granularity, filterParams, startDate, endDate]);

  useEffect(() => { loadTableData(); }, [loadTableData]);

  // Reset page when filters change
  useEffect(() => { setTablePage(1); }, [selectedUnderlying, selectedExpiry, startDate, endDate, searchSymbol, viewMode, granularity]);

  // ========== Upload ==========
  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragover(false);
    const file = e.dataTransfer.files[0];
    if (file && (file.name.endsWith('.csv') || file.name.endsWith('.parquet'))) {
      setUploadFile(file);
    }
  };

  const handleUpload = async () => {
    if (!uploadFile) return;
    setUploading(true);
    setUploadProgress(0);
    setUploadResult(null);
    try {
      const result = await uploadDataFile(
        uploadFile, uploadType, uploadSymbol, uploadGranularity,
        (pct) => setUploadProgress(pct),
      );
      setUploadResult({ ok: result.success, msg: result.message });
      if (result.success) {
        setUploadFile(null);
        // Refresh everything
        const unds = await getUnderlyings();
        setUnderlyings(unds);
        loadTableData();
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '未知错误';
      setUploadResult({ ok: false, msg });
    } finally {
      setUploading(false);
    }
  };

  // ========== Delete ==========
  const handleDelete = async () => {
    setShowDeleteConfirm(false);
    try {
      if (viewMode === 'option_bars' || viewMode === 'merged_bars') {
        const res = await deleteOptionBars(
          selectedUnderlying,
          selectedExpiry || undefined,
          startDate || undefined,
          endDate || undefined,
          searchSymbol.trim() || undefined,
        );
        setUploadResult({ ok: true, msg: `已删除 ${res.deleted} 条期权K线` });
      } else {
        const res = await deleteDailyBars(
          selectedUnderlying,
          startDate || undefined,
          endDate || undefined,
        );
        setUploadResult({ ok: true, msg: `已删除 ${res.deleted} 条标的K线` });
      }
      loadTableData();
    } catch {
      setUploadResult({ ok: false, msg: '删除失败' });
    }
  };

  // Build human-readable delete scope description
  const getDeleteDescription = () => {
    const parts: string[] = [];
    parts.push(`标的: ${selectedUnderlying}`);
    if (viewMode !== 'daily_bars' && selectedExpiry) parts.push(`到期日: ${selectedExpiry}`);
    if (startDate) parts.push(`开始日期: ${startDate}`);
    if (endDate) parts.push(`结束日期: ${endDate}`);
    if (viewMode !== 'daily_bars' && searchSymbol.trim()) parts.push(`合约搜索: ${searchSymbol.trim()}`);

    const hasFilter = selectedExpiry || startDate || endDate || (viewMode !== 'daily_bars' && searchSymbol.trim());
    const dataType = viewMode === 'daily_bars' ? '标的K线' : '期权K线';

    if (hasFilter) {
      return `确定删除以下筛选条件匹配的${dataType}数据？`;
    }
    return `确定删除 ${selectedUnderlying} 的全部${dataType}数据？`;
  };

  const getDeleteFilterSummary = () => {
    const filters: string[] = [];
    filters.push(`标的: ${selectedUnderlying}`);
    if (viewMode !== 'daily_bars' && selectedExpiry) filters.push(`到期日: ${selectedExpiry}`);
    if (startDate) filters.push(`开始日期 ≥ ${startDate}`);
    if (endDate) filters.push(`结束日期 ≤ ${endDate}`);
    if (viewMode !== 'daily_bars' && searchSymbol.trim()) filters.push(`合约包含: ${searchSymbol.trim()}`);
    return filters;
  };

  const totalPages = Math.ceil(tableTotal / PAGE_SIZE);

  // Whether to show option-related filters (expiry / search)
  const showOptionFilters = viewMode === 'option_bars' || viewMode === 'merged_bars';

  if (initLoading) {
    return (
      <div className="db-page">
        <div className="loading-container"><div className="spinner" /><span>加载中...</span></div>
      </div>
    );
  }

  return (
    <div className="db-page">
      {/* Stats Row — reflects current filters */}
      <div className="db-stats">
        <div className="db-stat-card">
          <span className="stat-value">{stats?.optionContractCount ?? 0}</span>
          <span className="stat-label">期权合约</span>
        </div>
        <div className="db-stat-card">
          <span className="stat-value">{(stats?.optionBarCount ?? 0).toLocaleString()}</span>
          <span className="stat-label">期权K线</span>
        </div>
        <div className="db-stat-card">
          <span className="stat-value">{(stats?.dailyBarCount ?? 0).toLocaleString()}</span>
          <span className="stat-label">标的K线</span>
        </div>
        <div className="db-stat-card">
          <span className="stat-value">{underlyings.length}</span>
          <span className="stat-label">标的数量</span>
        </div>
        {stats?.dateRange && (
          <div className="db-stat-card">
            <span className="stat-value" style={{ fontSize: 14 }}>
              {stats.dateRange.start} ~ {stats.dateRange.end}
            </span>
            <span className="stat-label">数据时间范围</span>
          </div>
        )}
      </div>

      {/* Toolbar */}
      <div className="db-toolbar">
        <button className="btn btn-primary" onClick={() => setShowUpload(!showUpload)}>
          {showUpload ? '收起上传' : '上传数据'}
        </button>
        <button className="btn btn-danger" onClick={() => setShowDeleteConfirm(true)}>
          删除数据
        </button>
        <div style={{ flex: 1 }} />
        <span className="tag tag-primary">{granularity === 'daily' ? '日级别' : '分钟级别'}</span>
      </div>

      {/* Upload Section */}
      {showUpload && (
        <div className="card">
          <div className="card-body">
            <div
              className={`upload-area ${dragover ? 'dragover' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setDragover(true); }}
              onDragLeave={() => setDragover(false)}
              onDrop={handleFileDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input ref={fileInputRef} type="file" accept=".csv,.parquet"
                style={{ display: 'none' }}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) setUploadFile(f); }}
              />
              <div className="upload-area-icon">📁</div>
              {uploadFile ? (
                <><h4>{uploadFile.name}</h4><p>{(uploadFile.size / 1024 / 1024).toFixed(1)} MB</p></>
              ) : (
                <><h4>拖拽文件到此处，或点击选择</h4><p>支持 CSV / Parquet 格式</p></>
              )}
            </div>
            {uploadFile && (
              <div className="upload-config">
                <div className="form-group">
                  <label>数据类型</label>
                  <select className="form-select" value={uploadType}
                    onChange={(e) => setUploadType(e.target.value as 'option' | 'underlying')}>
                    <option value="option">期权数据</option>
                    <option value="underlying">标的数据</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>标的代码</label>
                  <input className="form-input" value={uploadSymbol}
                    onChange={(e) => setUploadSymbol(e.target.value)}
                    placeholder="如 510050" style={{ width: 120 }} />
                </div>
                <div className="form-group">
                  <label>数据颗粒度</label>
                  <select className="form-select" value={uploadGranularity}
                    onChange={(e) => setUploadGranularity(e.target.value as Granularity)}>
                    <option value="daily">日级别</option>
                    <option value="minute">分钟级别</option>
                  </select>
                </div>
                <button className="btn btn-primary btn-lg" onClick={handleUpload} disabled={uploading}>
                  {uploading ? <><span className="spinner sm" /> 上传中 {uploadProgress}%</> : '开始上传'}
                </button>
              </div>
            )}

            {/* Column hints */}
            {uploadFile && (
              <div className="upload-hints">
                {uploadType === 'option' ? (
                  <>
                    <p className="upload-hints-title">期权数据 CSV 必需列：</p>
                    <div className="upload-hints-cols">
                      <span className="col-tag required">security_id</span>
                      <span className="col-tag required">trade_date</span>
                      <span className="col-tag required">last_edate</span>
                      <span className="col-tag required">exercise_price</span>
                      <span className="col-tag required">call_put</span>
                      <span className="col-tag required">open</span>
                      <span className="col-tag required">high</span>
                      <span className="col-tag required">low</span>
                      <span className="col-tag required">close</span>
                      <span className="col-tag required">implc_volatlty</span>
                      <span className="col-tag">volume</span>
                      <span className="col-tag">amount</span>
                      <span className="col-tag">delta</span>
                      <span className="col-tag">gamma</span>
                      <span className="col-tag">theta</span>
                      <span className="col-tag">vega</span>
                      <span className="col-tag">rho</span>
                    </div>
                    <p className="upload-hints-note">
                      若 CSV 包含 fund_open / fund_high / fund_low / fund_close / fund_volume / fund_amount 列，将自动提取并导入标的ETF日K线数据。若不包含，合并视图中标的数据将显示为空 (-)。
                    </p>
                  </>
                ) : (
                  <>
                    <p className="upload-hints-title">标的数据 CSV 必需列：</p>
                    <div className="upload-hints-cols">
                      <span className="col-tag required">trade_date</span>
                      <span className="col-tag required">open</span>
                      <span className="col-tag required">high</span>
                      <span className="col-tag required">low</span>
                      <span className="col-tag required">close</span>
                      <span className="col-tag">volume</span>
                      <span className="col-tag">amount</span>
                    </div>
                    <p className="upload-hints-note">
                      日期列也可命名为 date 或 datetime，系统会自动识别。
                    </p>
                  </>
                )}
              </div>
            )}

            {uploading && (
              <div style={{ marginTop: 12 }}>
                <div className="progress-bar">
                  <div className="progress-bar-fill" style={{ width: `${uploadProgress}%` }} />
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Result toast */}
      {uploadResult && (
        <div className={`db-toast ${uploadResult.ok ? 'success' : 'error'}`}>
          {uploadResult.msg}
          <button className="db-toast-close" onClick={() => setUploadResult(null)}>×</button>
        </div>
      )}

      {/* Filter Bar */}
      <div className="db-filter-bar">
        <div className="form-group">
          <label>标的</label>
          <select className="form-select" value={selectedUnderlying}
            onChange={(e) => setSelectedUnderlying(e.target.value)}>
            {underlyings.map((u) => (
              <option key={u.symbol} value={u.symbol}>{u.symbol} - {u.name}</option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label>查看数据</label>
          <select className="form-select" value={viewMode}
            onChange={(e) => setViewMode(e.target.value as ViewMode)}>
            <option value="option_bars">期权K线</option>
            <option value="daily_bars">标的K线</option>
            <option value="merged_bars">全部K线</option>
          </select>
        </div>

        {showOptionFilters && (
          <>
            <div className="form-group">
              <label>到期日</label>
              <select className="form-select" value={selectedExpiry}
                onChange={(e) => setSelectedExpiry(e.target.value)}>
                <option value="">全部</option>
                {expiries.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>搜索合约</label>
              <input className="form-input" placeholder="输入合约代码..."
                value={searchSymbol}
                onChange={(e) => setSearchSymbol(e.target.value)}
                style={{ minWidth: 160 }} />
            </div>
          </>
        )}

        <div className="form-group">
          <label>开始日期</label>
          <input type="date" className="form-input" value={startDate}
            onChange={(e) => setStartDate(e.target.value)} />
        </div>
        <div className="form-group">
          <label>结束日期</label>
          <input type="date" className="form-input" value={endDate}
            onChange={(e) => setEndDate(e.target.value)} />
        </div>

        <div className="form-group">
          <label>颗粒度</label>
          <select className="form-select" value={granularity}
            onChange={(e) => setGranularity(e.target.value as Granularity)}>
            <option value="daily">日级别</option>
            <option value="minute">分钟级别</option>
          </select>
        </div>
      </div>

      {/* Data Table */}
      <div className={`db-table-container ${viewMode === 'merged_bars' ? 'merged-scroll' : ''}`}>
        {granularity === 'minute' ? (
          <div className="empty-state">
            <div className="empty-state-icon">⏱</div>
            <h3>暂无分钟级别数据</h3>
            <p>当前仅支持日级别数据，分钟级别数据支持即将上线</p>
          </div>
        ) : tableLoading ? (
          <div className="loading-container"><div className="spinner" /><span>加载数据...</span></div>
        ) : viewMode === 'option_bars' ? (
          <OptionBarsTable rows={optionRows} hoverCell={hoverCell} onHoverCell={setHoverCell} />
        ) : viewMode === 'daily_bars' ? (
          <DailyBarsTable rows={dailyRows} hoverCell={hoverCell} onHoverCell={setHoverCell} />
        ) : (
          <MergedBarsTable rows={mergedRows} hoverCell={hoverCell} onHoverCell={setHoverCell} />
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="db-pagination">
          <button disabled={tablePage <= 1} onClick={() => setTablePage((p) => p - 1)}>上一页</button>
          <span>第 {tablePage} / {totalPages} 页 (共 {tableTotal.toLocaleString()} 条)</span>
          <button disabled={tablePage >= totalPages} onClick={() => setTablePage((p) => p + 1)}>下一页</button>
        </div>
      )}

      {/* Delete Confirm Modal */}
      {showDeleteConfirm && (
        <div className="modal-overlay" onClick={() => setShowDeleteConfirm(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>确认删除</h3>
              <button className="modal-close" onClick={() => setShowDeleteConfirm(false)}>×</button>
            </div>
            <div className="modal-body">
              <p style={{ fontWeight: 600 }}>{getDeleteDescription()}</p>
              <ul style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '10px 0', paddingLeft: 20 }}>
                {getDeleteFilterSummary().map((f, i) => <li key={i}>{f}</li>)}
              </ul>
              <p style={{ color: 'var(--danger)', fontSize: 13, marginTop: 8 }}>此操作不可撤销，删除的数据将无法恢复。</p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowDeleteConfirm(false)}>取消</button>
              <button className="btn btn-danger" onClick={handleDelete}>确认删除</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ===== Sub-components ===== */

interface TableHoverProps {
  hoverCell: { row: number; col: number } | null;
  onHoverCell: (cell: { row: number; col: number } | null) => void;
}

function cellClass(ri: number, ci: number, hover: { row: number; col: number } | null, extra?: string) {
  const parts: string[] = [];
  if (extra) parts.push(extra);
  if (hover) {
    if (hover.row === ri && hover.col === ci) parts.push('ch-active');
    else if (hover.row === ri) parts.push('ch-row');
    else if (hover.col === ci) parts.push('ch-col');
  }
  return parts.join(' ') || undefined;
}

function OptionBarsTable({ rows, hoverCell, onHoverCell }: { rows: OptionBarRow[] } & TableHoverProps) {
  if (rows.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">📋</div>
        <h3>暂无数据</h3>
        <p>请调整筛选条件或上传数据文件</p>
      </div>
    );
  }
  return (
    <table className="db-table" onMouseLeave={() => onHoverCell(null)}>
      <thead>
        <tr>
          <th>日期</th><th>合约</th><th>开盘</th><th>最高</th><th>最低</th><th>收盘</th>
          <th>成交量</th><th>IV</th><th>Delta</th><th>Gamma</th><th>Theta</th><th>Vega</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, ri) => (
          <tr key={`${r.trade_date}-${r.symbol}-${ri}`}>
            {[
              r.trade_date,
              r.symbol,
              r.open?.toFixed(4),
              r.high?.toFixed(4),
              r.low?.toFixed(4),
              r.close?.toFixed(4),
              r.volume?.toLocaleString(),
              r.iv != null ? (r.iv * 100).toFixed(1) + '%' : '-',
              r.delta?.toFixed(3) ?? '-',
              r.gamma?.toFixed(3) ?? '-',
              r.theta?.toFixed(3) ?? '-',
              r.vega?.toFixed(3) ?? '-',
            ].map((val, ci) => (
              <td
                key={ci}
                className={cellClass(ri, ci, hoverCell, ci >= 2 ? 'num' : ci === 1 ? 'mono' : undefined)}
                onMouseEnter={() => onHoverCell({ row: ri, col: ci })}
              >
                {val}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function DailyBarsTable({ rows, hoverCell, onHoverCell }: { rows: DailyBarRow[] } & TableHoverProps) {
  if (rows.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">📋</div>
        <h3>暂无标的K线数据</h3>
        <p>请上传标的ETF价格数据</p>
      </div>
    );
  }
  return (
    <table className="db-table" onMouseLeave={() => onHoverCell(null)}>
      <thead>
        <tr>
          <th>日期</th><th>开盘</th><th>最高</th><th>最低</th><th>收盘</th>
          <th>成交量</th><th>成交额</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, ri) => (
          <tr key={`${r.trade_date}-${ri}`}>
            {[
              r.trade_date,
              r.open?.toFixed(4),
              r.high?.toFixed(4),
              r.low?.toFixed(4),
              r.close?.toFixed(4),
              r.volume?.toLocaleString(),
              r.amount?.toLocaleString(),
            ].map((val, ci) => (
              <td
                key={ci}
                className={cellClass(ri, ci, hoverCell, ci >= 1 ? 'num' : undefined)}
                onMouseEnter={() => onHoverCell({ row: ri, col: ci })}
              >
                {val}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function MergedBarsTable({ rows, hoverCell, onHoverCell }: { rows: MergedBarRow[] } & TableHoverProps) {
  const firstRowRef = useRef<HTMLTableRowElement>(null);
  const [firstRowHeight, setFirstRowHeight] = useState(0);

  useEffect(() => {
    if (firstRowRef.current) {
      setFirstRowHeight(firstRowRef.current.getBoundingClientRect().height);
    }
  }, [rows]);

  if (rows.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">📋</div>
        <h3>暂无合并K线数据</h3>
        <p>请上传期权数据，标的数据将自动匹配</p>
      </div>
    );
  }
  return (
    <table className="db-table db-table-merged" onMouseLeave={() => onHoverCell(null)}>
      <thead>
        <tr ref={firstRowRef}>
          <th className="sticky-col sticky-col-1">日期</th>
          <th className="sticky-col sticky-col-2">合约</th>
          <th className="group-header-option" colSpan={4}>期权价格</th>
          <th>成交量</th>
          <th>IV</th><th>Delta</th><th>Gamma</th><th>Theta</th><th>Vega</th><th>Rho</th>
          <th className="group-header-fund" colSpan={4}>标的价格</th>
          <th>标的量</th><th>标的额</th>
        </tr>
        <tr className="sub-header">
          <th className="sticky-col sticky-col-1" style={{ top: firstRowHeight || undefined }}></th>
          <th className="sticky-col sticky-col-2" style={{ top: firstRowHeight || undefined }}></th>
          {['开盘','最高','最低','收盘','','','','','','','','开盘','最高','最低','收盘','',''].map((label, i) => (
            <th key={i} style={{ top: firstRowHeight || undefined }}>{label}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, ri) => {
          const vals: (string | undefined)[] = [
            r.trade_date,
            r.symbol,
            r.open?.toFixed(4),
            r.high?.toFixed(4),
            r.low?.toFixed(4),
            r.close?.toFixed(4),
            r.volume?.toLocaleString(),
            r.iv != null ? (r.iv * 100).toFixed(1) + '%' : '-',
            r.delta?.toFixed(3) ?? '-',
            r.gamma?.toFixed(3) ?? '-',
            r.theta?.toFixed(3) ?? '-',
            r.vega?.toFixed(3) ?? '-',
            r.rho?.toFixed(3) ?? '-',
            r.fund_open != null ? r.fund_open.toFixed(4) : '-',
            r.fund_high != null ? r.fund_high.toFixed(4) : '-',
            r.fund_low != null ? r.fund_low.toFixed(4) : '-',
            r.fund_close != null ? r.fund_close.toFixed(4) : '-',
            r.fund_volume != null ? r.fund_volume.toLocaleString() : '-',
            r.fund_amount != null ? r.fund_amount.toLocaleString() : '-',
          ];
          return (
            <tr key={`${r.trade_date}-${r.symbol}-${ri}`}>
              {vals.map((val, ci) => (
                <td
                  key={ci}
                  className={[
                    ci === 0 ? 'sticky-col sticky-col-1' : '',
                    ci === 1 ? 'sticky-col sticky-col-2 mono' : '',
                    ci >= 2 ? 'num' : '',
                    hoverCell && hoverCell.row === ri && hoverCell.col === ci ? 'ch-active' : '',
                    hoverCell && hoverCell.row === ri && hoverCell.col !== ci ? 'ch-row' : '',
                    hoverCell && hoverCell.col === ci && hoverCell.row !== ri ? 'ch-col' : '',
                  ].filter(Boolean).join(' ') || undefined}
                  onMouseEnter={() => onHoverCell({ row: ri, col: ci })}
                >
                  {val}
                </td>
              ))}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
