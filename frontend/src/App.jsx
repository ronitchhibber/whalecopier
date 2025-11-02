import { useState, useEffect } from 'react';

export default function App() {
  const [stats, setStats] = useState(null);
  const [whales, setWhales] = useState([]);
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('dashboard');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, whalesRes, tradesRes] = await Promise.all([
          fetch('/api/stats/summary'),
          fetch('/api/whales?limit=20'),
          fetch('/api/trades?limit=10')
        ]);
        setStats(await statsRes.json());
        setWhales(await whalesRes.json());
        setTrades(await tradesRes.json());
      } catch (error) {
        console.error('API Error:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="flex items-center justify-center min-h-screen">Loading...</div>;

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900">
      <nav className="bg-gray-800/50 border-b border-gray-700 backdrop-blur-lg">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
              Whale Trader v0.1
            </h1>
            <div className="flex gap-4">
              {['dashboard', 'whales', 'trades'].map((tab) => (
                <button key={tab} onClick={() => setActiveTab(tab)} className={\`px-4 py-2 rounded-lg font-medium transition-all \${activeTab === tab ? 'bg-blue-600 text-white' : 'bg-gray-700/50 text-gray-300 hover:bg-gray-700'}\`}>
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </div>
      </nav>

      <main className="container mx-auto px-6 py-8">
        {activeTab === 'dashboard' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-8">
            {[
              { label: 'Total Whales', value: stats?.total_whales, color: 'blue' },
              { label: '24h Trades', value: stats?.trades_24h, color: 'green' },
              { label: '24h Volume', value: \`$\${stats?.volume_24h?.toLocaleString()}\`, color: 'purple' },
              { label: 'Paper Balance', value: \`$\${stats?.paper_balance?.toLocaleString()}\`, color: 'yellow' },
              { label: 'Paper P&L', value: \`$\${stats?.paper_pnl?.toLocaleString()}\`, color: stats?.paper_pnl >= 0 ? 'green' : 'red' },
            ].map((stat) => (
              <div key={stat.label} className="bg-gray-800/50 backdrop-blur-lg rounded-xl p-6 border border-gray-700">
                <div className="text-gray-400 text-sm mb-2">{stat.label}</div>
                <div className={\`text-3xl font-bold text-\${stat.color}-400\`}>{stat.value}</div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'whales' && (
          <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 overflow-hidden">
            <div className="p-6 border-b border-gray-700"><h2 className="text-2xl font-bold">Top Whales</h2></div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-700/50">
                  <tr>{['Whale', 'Tier', 'Win Rate', 'Sharpe', 'Total P&L', 'Volume', 'Trades'].map((header) => (<th key={header} className="px-6 py-4 text-left text-sm font-semibold text-gray-300">{header}</th>))}</tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {whales.map((whale) => (
                    <tr key={whale.address} className="hover:bg-gray-700/30 transition-colors">
                      <td className="px-6 py-4">
                        <div><div className="font-medium text-white">{whale.pseudonym}</div><div className="text-xs text-gray-400">{whale.address.slice(0, 10)}...</div></div>
                      </td>
                      <td className="px-6 py-4"><span className={\`px-3 py-1 rounded-full text-xs font-bold \${whale.tier === 'MEGA' ? 'bg-purple-500/20 text-purple-300' : whale.tier === 'HIGH' ? 'bg-blue-500/20 text-blue-300' : 'bg-green-500/20 text-green-300'}\`}>{whale.tier}</span></td>
                      <td className="px-6 py-4 text-green-400 font-medium">{whale.win_rate}%</td>
                      <td className="px-6 py-4 text-blue-400 font-medium">{whale.sharpe_ratio}</td>
                      <td className="px-6 py-4 text-yellow-400 font-bold">\${whale.total_pnl.toLocaleString()}</td>
                      <td className="px-6 py-4 text-gray-300">\${whale.total_volume.toLocaleString()}</td>
                      <td className="px-6 py-4 text-gray-300">{whale.total_trades}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === 'trades' && (
          <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl border border-gray-700 overflow-hidden">
            <div className="p-6 border-b border-gray-700"><h2 className="text-2xl font-bold">Recent Trades</h2></div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-700/50">
                  <tr>{['Time', 'Whale', 'Side', 'Size', 'Price', 'Amount'].map((header) => (<th key={header} className="px-6 py-4 text-left text-sm font-semibold text-gray-300">{header}</th>))}</tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {trades.map((trade) => (
                    <tr key={trade.id} className="hover:bg-gray-700/30 transition-colors">
                      <td className="px-6 py-4 text-gray-400 text-sm">{new Date(trade.timestamp).toLocaleString()}</td>
                      <td className="px-6 py-4"><div className="font-medium text-white">{trade.whale_name}</div></td>
                      <td className="px-6 py-4"><span className={\`px-3 py-1 rounded-full text-xs font-bold \${trade.side === 'BUY' ? 'bg-green-500/20 text-green-300' : 'bg-red-500/20 text-red-300'}\`}>{trade.side}</span></td>
                      <td className="px-6 py-4 text-gray-300">{trade.size.toFixed(2)}</td>
                      <td className="px-6 py-4 text-blue-400">\${trade.price.toFixed(2)}</td>
                      <td className="px-6 py-4 text-yellow-400 font-medium">\${trade.amount.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      <footer className="bg-gray-800/50 border-t border-gray-700 mt-12">
        <div className="container mx-auto px-6 py-4 text-center text-gray-400 text-sm">
          Whale Trader v0.1 - Real-time Polymarket Copy Trading System | API: http://localhost:8000
        </div>
      </footer>
    </div>
  );
}
