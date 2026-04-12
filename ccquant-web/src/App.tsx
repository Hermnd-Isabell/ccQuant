import { Routes, Route, NavLink, Navigate } from 'react-router-dom';
import DatabasePage from './pages/DatabasePage';
import VisualizationPage from './pages/VisualizationPage';
import StrategyEditorPage from './pages/StrategyEditorPage';
import BacktestPage from './pages/BacktestPage';
import './App.css';

function App() {
  return (
    <div className="app">
      <header className="header">
        <div className="logo">
          <div className="logo-icon">cc</div>
          ccQuant
        </div>
        <nav className="nav">
          <NavLink to="/database" className={({ isActive }) => isActive ? 'active' : ''}>
            数据库
          </NavLink>
          <NavLink to="/visualization" className={({ isActive }) => isActive ? 'active' : ''}>
            可视化
          </NavLink>
          <NavLink to="/strategy" className={({ isActive }) => isActive ? 'active' : ''}>
            策略编写
          </NavLink>
          <NavLink to="/backtest" className={({ isActive }) => isActive ? 'active' : ''}>
            策略回测
          </NavLink>
        </nav>
      </header>

      <main className="main-content">
        <Routes>
          <Route path="/" element={<Navigate to="/database" replace />} />
          <Route path="/database" element={<DatabasePage />} />
          <Route path="/visualization" element={<VisualizationPage />} />
          <Route path="/strategy" element={<StrategyEditorPage />} />
          <Route path="/backtest" element={<BacktestPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
