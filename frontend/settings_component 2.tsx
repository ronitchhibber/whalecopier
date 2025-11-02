import React, { useState, useEffect } from 'react';
import './settings.css';

interface DisplayFormat {
  id: string;
  name: string;
  lines: number;
  description: string;
  preview: string;
}

const SettingsComponent: React.FC = () => {
  const [activeTab, setActiveTab] = useState('display');
  const [selectedFormat, setSelectedFormat] = useState('mini');
  const [settings, setSettings] = useState({
    display: {
      format: 'mini',
      refreshRate: 5,
      showAlerts: true,
      showEmojis: true,
      terminalWidth: 80,
      colorEnabled: false
    },
    trading: {
      mode: 'paper',
      initialBalance: 10000,
      basePositionSize: 5,
      maxPositionSize: 20,
      stopLoss: 10,
      takeProfit: 20
    }
  });

  const displayFormats: DisplayFormat[] = [
    {
      id: 'single',
      name: 'Single Line',
      lines: 1,
      description: 'Ultra minimal scrolling display',
      preview: 'WHALE TRADER | P&L:+$8.5K Win:73% Sharpe:2.34 | 🟢'
    },
    {
      id: 'status',
      name: 'Status Bar',
      lines: 2,
      description: 'Minimal status bar',
      preview: 'WHALE TRADER │ P&L:+$8.5K Win:73%\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
    },
    {
      id: 'metrics',
      name: 'Metrics',
      lines: 4,
      description: 'Key numbers only',
      preview: 'P&L:+$8.5K │ Win:73% │ Sharpe:2.34\nWhales:25  │ Signals:145/d │ VaR:12%\nVolume:$125K │ Trades:1456\nLast: BUY BTC>100k +12.5%'
    },
    {
      id: 'ticker',
      name: 'Ticker',
      lines: 5,
      description: 'Essential info ticker',
      preview: '══ WHALE TRADER ══\nP&L:+$8.5K Win:73% Sharpe:2.34\nWhales:25 Signals:145 Trades:1456\nLast: BUY BTC>100k $5K +12.5%\nSystems: DB:🟢 API:🟢 WS:🟢'
    },
    {
      id: 'grid',
      name: 'Grid',
      lines: 8,
      description: 'Organized metric grid',
      preview: 'WHALE TRADER  22:30:45\n┌─────────────┬─────────────┬─────────────┐\n│ P&L: +$8.5K │ Win: 73%    │ Sharpe: 2.34│\n│ DD: 8%      │ VaR: 12%    │ Trades: 1456│\n│ Whales: 25  │ Signals:145 │ Exp: $45K   │\n└─────────────┴─────────────┴─────────────┘\nLast: BUY BTC>100k $5K +12.5%\nStatus: 🟢 🟢 🟢 🟢 🟡'
    },
    {
      id: 'mini',
      name: 'Mini',
      lines: 10,
      description: 'Balanced information view',
      preview: 'WHALE TRADER 22:30:45\nDB:🟢 API:🟢 WS:🟢 Engine:🟢 Monitor:🟡\nTrades:1456 Win:73% P&L:+$8.5K\nWhales:25 Signals:145 Exposure:$45K\nLast: BUY BTC>100k $5K +12.5%\n⚠ Loss limit 8.5%\n[Q]uit [R]efresh'
    },
    {
      id: 'compact',
      name: 'Compact',
      lines: 15,
      description: 'Full monitoring dashboard',
      preview: 'POLYMARKET WHALE TRADER - 22:30:45\n────────────────────────────────────\nStatus: DB:🟢 API:🟢 WS:🟢 Engine:🟢\n\nPerformance:\n  Trades:1456 WinRate:73% Vol:$125K\n  Sharpe:2.34 DD:8% VaR:12%\n\nRecent:\n  BUY  0x1234→BTC>100k    $5K  +12.5%\n  SELL 0x5678→Trump2024   $2.5K -3.2%\n\nAlert: ⚠ Approaching daily loss limit\n\n[Q]uit [R]efresh [D]etails'
    }
  ];

  const saveSettings = async () => {
    try {
      const response = await fetch('/api/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(settings),
      });

      if (response.ok) {
        showNotification('Settings saved successfully!');
      }
    } catch (error) {
      console.error('Failed to save settings:', error);
      showNotification('Failed to save settings', 'error');
    }
  };

  const showNotification = (message: string, type: string = 'success') => {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
      notification.remove();
    }, 3000);
  };

  return (
    <div className="settings-container">
      <div className="settings-header">
        <h2>Trading Settings</h2>
      </div>

      <div className="settings-tabs">
        <button
          className={`tab-button ${activeTab === 'display' ? 'active' : ''}`}
          onClick={() => setActiveTab('display')}
        >
          Display Format
        </button>
        <button
          className={`tab-button ${activeTab === 'paper' ? 'active' : ''}`}
          onClick={() => setActiveTab('paper')}
        >
          Paper Trading
        </button>
        <button
          className={`tab-button ${activeTab === 'risk' ? 'active' : ''}`}
          onClick={() => setActiveTab('risk')}
        >
          Risk Management
        </button>
        <button
          className={`tab-button ${activeTab === 'whales' ? 'active' : ''}`}
          onClick={() => setActiveTab('whales')}
        >
          Whale Selection
        </button>
      </div>

      {activeTab === 'display' && (
        <div className="tab-content">
          <div className="section">
            <h3>Display Format Selection</h3>
            <div className="format-grid">
              {displayFormats.map(format => (
                <div
                  key={format.id}
                  className={`format-card ${selectedFormat === format.id ? 'selected' : ''}`}
                  onClick={() => {
                    setSelectedFormat(format.id);
                    setSettings({...settings, display: {...settings.display, format: format.id}});
                  }}
                >
                  <div className="format-header">
                    <span className="format-name">{format.name}</span>
                    <span className="format-lines">{format.lines} lines</span>
                  </div>
                  <div className="format-description">{format.description}</div>
                  <div className="format-preview">
                    <pre>{format.preview}</pre>
                  </div>
                  {selectedFormat === format.id && (
                    <div className="format-selected-badge">✓</div>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="section">
            <h3>Display Preferences</h3>
            <div className="settings-grid">
              <div className="setting-row">
                <label>Refresh Rate (seconds)</label>
                <input
                  type="range"
                  min="1"
                  max="60"
                  value={settings.display.refreshRate}
                  onChange={(e) => setSettings({
                    ...settings,
                    display: {...settings.display, refreshRate: parseInt(e.target.value)}
                  })}
                />
                <span>{settings.display.refreshRate}s</span>
              </div>

              <div className="setting-row">
                <label>Show Alerts</label>
                <div
                  className={`toggle ${settings.display.showAlerts ? 'active' : ''}`}
                  onClick={() => setSettings({
                    ...settings,
                    display: {...settings.display, showAlerts: !settings.display.showAlerts}
                  })}
                >
                  <div className="toggle-slider"></div>
                </div>
              </div>

              <div className="setting-row">
                <label>Show Emojis</label>
                <div
                  className={`toggle ${settings.display.showEmojis ? 'active' : ''}`}
                  onClick={() => setSettings({
                    ...settings,
                    display: {...settings.display, showEmojis: !settings.display.showEmojis}
                  })}
                >
                  <div className="toggle-slider"></div>
                </div>
              </div>

              <div className="setting-row">
                <label>Terminal Width</label>
                <input
                  type="number"
                  value={settings.display.terminalWidth}
                  min="40"
                  max="200"
                  onChange={(e) => setSettings({
                    ...settings,
                    display: {...settings.display, terminalWidth: parseInt(e.target.value)}
                  })}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'paper' && (
        <div className="tab-content">
          <div className="section">
            <h3>Paper Trading</h3>
            <div className="settings-grid">
              <div className="setting-row">
                <label>Initial Balance ($)</label>
                <input
                  type="number"
                  value={settings.trading.initialBalance}
                  onChange={(e) => setSettings({
                    ...settings,
                    trading: {...settings.trading, initialBalance: parseInt(e.target.value)}
                  })}
                />
              </div>

              <div className="setting-row">
                <label>Base Position Size (%)</label>
                <input
                  type="number"
                  value={settings.trading.basePositionSize}
                  min="1"
                  max="100"
                  onChange={(e) => setSettings({
                    ...settings,
                    trading: {...settings.trading, basePositionSize: parseInt(e.target.value)}
                  })}
                />
              </div>

              <div className="setting-row">
                <label>Max Position Size (%)</label>
                <input
                  type="number"
                  value={settings.trading.maxPositionSize}
                  min="1"
                  max="100"
                  onChange={(e) => setSettings({
                    ...settings,
                    trading: {...settings.trading, maxPositionSize: parseInt(e.target.value)}
                  })}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="settings-footer">
        <button className="save-button" onClick={saveSettings}>
          💾 Save Settings
        </button>
      </div>
    </div>
  );
};

export default SettingsComponent;