import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  Plus,
  Trash2,
  RefreshCw,
  Activity,
  Database,
  Globe,
  Clock,
  Terminal,
  Zap,
  BarChart3,
  CheckCircle2,
  XCircle,
  AlertCircle,
} from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ─── TYPES ───────────────────────────────────────────────────────────────────
interface SearchConfig {
  id: number;
  fraza: string;
  min_cena: number;
  max_cena: number;
  active: boolean;
  created_at: string;
}

interface LogEntry {
  id: number;
  level: string;
  message: string;
  created_at: string;
}

interface Stats {
  total: number;
  by_service: Record<string, number>;
}

// ─── MOCK DATA / LOCAL STORAGE ───────────────────────────────────────────────
const STORAGE_KEY = "vintedbot_searches";
const LOGS_KEY = "vintedbot_logs";

function loadSearches(): SearchConfig[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return [
    { id: 1, fraza: "gogle", min_cena: 300, max_cena: 2000, active: true, created_at: new Date().toISOString() },
  ];
}

function saveSearches(searches: SearchConfig[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(searches));
}

function loadLogs(): LogEntry[] {
  try {
    const raw = localStorage.getItem(LOGS_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return [];
}

function addLog(level: string, message: string) {
  const logs = loadLogs();
  logs.unshift({
    id: Date.now(),
    level,
    message,
    created_at: new Date().toISOString(),
  });
  localStorage.setItem(LOGS_KEY, JSON.stringify(logs.slice(0, 200)));
}

// ─── COMPONENTS ──────────────────────────────────────────────────────────────

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("bg-white/80 backdrop-blur-sm rounded-2xl border border-slate-200/60 shadow-sm", className)}>
      {children}
    </div>
  );
}

function Badge({ children, variant = "default" }: { children: React.ReactNode; variant?: "default" | "success" | "warning" | "danger" }) {
  const variants = {
    default: "bg-slate-100 text-slate-700",
    success: "bg-emerald-100 text-emerald-700",
    warning: "bg-amber-100 text-amber-700",
    danger: "bg-rose-100 text-rose-700",
  };
  return (
    <span className={cn("inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium", variants[variant])}>
      {children}
    </span>
  );
}

export default function App() {
  const [searches, setSearches] = useState<SearchConfig[]>(loadSearches);
  const [logs, setLogs] = useState<LogEntry[]>(loadLogs);
  const [stats, setStats] = useState<Stats>({ total: 0, by_service: {} });
  const [isChecking, setIsChecking] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newFraza, setNewFraza] = useState("");
  const [newMin, setNewMin] = useState(300);
  const [newMax, setNewMax] = useState(2000);
  const [activeTab, setActiveTab] = useState<"dashboard" | "logs" | "config">("dashboard");
  const [lastCheck, setLastCheck] = useState<string | null>(null);

  useEffect(() => {
    saveSearches(searches);
  }, [searches]);

  useEffect(() => {
    const interval = setInterval(() => {
      setLogs(loadLogs());
      // Simulate stats from localStorage
      const seen = JSON.parse(localStorage.getItem("vintedbot_seen") || "{}");
      setStats({
        total: Object.keys(seen).length,
        by_service: seen.by_service || {},
      });
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleCheck = useCallback(async () => {
    setIsChecking(true);
    addLog("INFO", "Ręczne sprawdzanie uruchomione z panelu web");

    // Simulate checking delay
    await new Promise((r) => setTimeout(r, 2500));

    const activeSearches = searches.filter((s) => s.active);
    for (const s of activeSearches) {
      addLog("INFO", `Sprawdzam: ${s.fraza} (${s.min_cena}-${s.max_cena} PLN)`);
      // Simulate found offers
      const services = ["OLX", "Vinted", "Allegro"];
      for (const serwis of services) {
        const count = Math.floor(Math.random() * 4);
        if (count > 0) {
          addLog("INFO", `${serwis}: znaleziono ${count} ofert dla "${s.fraza}"`);
        }
      }
    }

    addLog("SUCCESS", "Sprawdzanie zakończone");
    setLastCheck(new Date().toLocaleTimeString("pl-PL"));
    setIsChecking(false);
    setLogs(loadLogs());
  }, [searches]);

  const handleAdd = () => {
    if (!newFraza.trim()) return;
    const id = Date.now();
    const updated = [
      ...searches,
      {
        id,
        fraza: newFraza.trim(),
        min_cena: newMin,
        max_cena: newMax,
        active: true,
        created_at: new Date().toISOString(),
      },
    ];
    setSearches(updated);
    addLog("INFO", `Dodano wyszukiwanie ID ${id}: ${newFraza}`);
    setNewFraza("");
    setShowAddForm(false);
    setLogs(loadLogs());
  };

  const handleRemove = (id: number) => {
    setSearches(searches.filter((s) => s.id !== id));
    addLog("INFO", `Usunięto wyszukiwanie ID ${id}`);
    setLogs(loadLogs());
  };

  const handleToggle = (id: number) => {
    setSearches(
      searches.map((s) =>
        s.id === id ? { ...s, active: !s.active } : s
      )
    );
    const s = searches.find((x) => x.id === id);
    if (s) {
      addLog("INFO", `Wyszukiwanie ID ${id} ${s.active ? "wyłączone" : "włączone"}`);
    }
    setLogs(loadLogs());
  };

  const handleClear = () => {
    if (confirm("Na pewno wyczyścić bazę seen_offers?")) {
      localStorage.setItem("vintedbot_seen", "{}");
      addLog("WARNING", "Wyczyszczono bazę seen_offers");
      setLogs(loadLogs());
    }
  };

  const activeCount = searches.filter((s) => s.active).length;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-gray-50 to-slate-100 text-slate-800">
      {/* HEADER */}
      <header className="sticky top-0 z-50 bg-white/70 backdrop-blur-md border-b border-slate-200/60">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold bg-gradient-to-r from-slate-800 to-slate-600 bg-clip-text text-transparent">
                VintedBot Panel
              </h1>
              <p className="text-xs text-slate-500">Monitor ogłoszeń OLX · Vinted · Allegro</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCheck}
              disabled={isChecking}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all",
                isChecking
                  ? "bg-slate-100 text-slate-400 cursor-not-allowed"
                  : "bg-emerald-600 hover:bg-emerald-700 text-white shadow-lg shadow-emerald-600/20 hover:shadow-emerald-600/30 active:scale-95"
              )}
            >
              <RefreshCw className={cn("w-4 h-4", isChecking && "animate-spin")} />
              {isChecking ? "Sprawdzam..." : "Sprawdź teraz"}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        {/* STATS ROW */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500 mb-1">Aktywne wyszukiwania</p>
                <p className="text-3xl font-bold text-slate-800">{activeCount}</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center">
                <Search className="w-6 h-6 text-emerald-600" />
              </div>
            </div>
          </Card>
          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500 mb-1">Ofert w bazie</p>
                <p className="text-3xl font-bold text-slate-800">{stats.total}</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center">
                <Database className="w-6 h-6 text-blue-600" />
              </div>
            </div>
          </Card>
          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500 mb-1">Ostatnie sprawdzenie</p>
                <p className="text-2xl font-bold text-slate-800">{lastCheck || "—"}</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-amber-50 flex items-center justify-center">
                <Clock className="w-6 h-6 text-amber-600" />
              </div>
            </div>
          </Card>
          <Card className="p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500 mb-1">Status bota</p>
                <div className="flex items-center gap-2">
                  <span className="relative flex h-3 w-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500" />
                  </span>
                  <span className="text-lg font-bold text-emerald-600">Online</span>
                </div>
              </div>
              <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center">
                <Activity className="w-6 h-6 text-emerald-600" />
              </div>
            </div>
          </Card>
        </div>

        {/* TABS */}
        <div className="flex gap-2 mb-6">
          {(["dashboard", "logs", "config"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                "px-4 py-2 rounded-xl text-sm font-medium transition-all",
                activeTab === tab
                  ? "bg-slate-800 text-white shadow-lg"
                  : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
              )}
            >
              {tab === "dashboard" && <span className="flex items-center gap-2"><BarChart3 className="w-4 h-4" /> Dashboard</span>}
              {tab === "logs" && <span className="flex items-center gap-2"><Terminal className="w-4 h-4" /> Logi</span>}
              {tab === "config" && <span className="flex items-center gap-2"><Globe className="w-4 h-4" /> Konfiguracja</span>}
            </button>
          ))}
        </div>

        <AnimatePresence mode="wait">
          {activeTab === "dashboard" && (
            <motion.div
              key="dashboard"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-6"
            >
              {/* SEARCHES */}
              <Card className="overflow-hidden">
                <div className="p-5 border-b border-slate-100 flex items-center justify-between">
                  <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                    <Search className="w-5 h-5 text-emerald-600" />
                    Wyszukiwania
                  </h2>
                  <button
                    onClick={() => setShowAddForm(!showAddForm)}
                    className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium transition-colors"
                  >
                    <Plus className="w-4 h-4" />
                    Dodaj
                  </button>
                </div>

                <AnimatePresence>
                  {showAddForm && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="p-5 bg-slate-50/50 border-b border-slate-100">
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                          <div>
                            <label className="block text-xs font-medium text-slate-500 mb-1">Fraza</label>
                            <input
                              value={newFraza}
                              onChange={(e) => setNewFraza(e.target.value)}
                              placeholder="np. gogle"
                              className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-slate-500 mb-1">Min cena (PLN)</label>
                            <input
                              type="number"
                              value={newMin}
                              onChange={(e) => setNewMin(Number(e.target.value))}
                              className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-slate-500 mb-1">Max cena (PLN)</label>
                            <input
                              type="number"
                              value={newMax}
                              onChange={(e) => setNewMax(Number(e.target.value))}
                              className="w-full px-3 py-2 rounded-lg border border-slate-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                            />
                          </div>
                        </div>
                        <div className="mt-4 flex justify-end gap-2">
                          <button
                            onClick={() => setShowAddForm(false)}
                            className="px-4 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-100 transition-colors"
                          >
                            Anuluj
                          </button>
                          <button
                            onClick={handleAdd}
                            className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium transition-colors"
                          >
                            Zapisz
                          </button>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                <div className="divide-y divide-slate-100">
                  {searches.length === 0 && (
                    <div className="p-8 text-center text-slate-400">
                      <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p>Brak wyszukiwań. Dodaj pierwsze powyżej.</p>
                    </div>
                  )}
                  {searches.map((s) => (
                    <motion.div
                      key={s.id}
                      layout
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="p-4 flex items-center justify-between hover:bg-slate-50/50 transition-colors"
                    >
                      <div className="flex items-center gap-4">
                        <button
                          onClick={() => handleToggle(s.id)}
                          className={cn(
                            "w-10 h-6 rounded-full transition-colors relative",
                            s.active ? "bg-emerald-500" : "bg-slate-300"
                          )}
                        >
                          <span
                            className={cn(
                              "absolute top-1 w-4 h-4 rounded-full bg-white shadow-sm transition-all",
                              s.active ? "left-5" : "left-1"
                            )}
                          />
                        </button>
                        <div>
                          <p className="font-semibold text-slate-800">{s.fraza}</p>
                          <p className="text-xs text-slate-500">
                            {s.min_cena} - {s.max_cena} PLN · ID {s.id}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={s.active ? "success" : "default"}>
                          {s.active ? "Aktywne" : "Wyłączone"}
                        </Badge>
                        <button
                          onClick={() => handleRemove(s.id)}
                          className="p-2 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </motion.div>
                  ))}
                </div>
              </Card>

              {/* SERVICES */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[
                  { name: "OLX", color: "text-emerald-600", bg: "bg-emerald-50", count: stats.by_service["OLX"] || 0 },
                  { name: "Vinted", color: "text-teal-600", bg: "bg-teal-50", count: stats.by_service["Vinted"] || 0 },
                  { name: "Allegro", color: "text-orange-600", bg: "bg-orange-50", count: stats.by_service["Allegro"] || 0 },
                ].map((svc) => (
                  <Card key={svc.name} className="p-5">
                    <div className="flex items-center gap-3">
                      <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center", svc.bg)}>
                        <Globe className={cn("w-5 h-5", svc.color)} />
                      </div>
                      <div>
                        <p className="font-semibold text-slate-800">{svc.name}</p>
                        <p className="text-xs text-slate-500">{svc.count} ofert w bazie</p>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </motion.div>
          )}

          {activeTab === "logs" && (
            <motion.div
              key="logs"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
            >
              <Card className="overflow-hidden">
                <div className="p-5 border-b border-slate-100 flex items-center justify-between">
                  <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                    <Terminal className="w-5 h-5 text-slate-600" />
                    Logi
                  </h2>
                  <button
                    onClick={() => {
                      localStorage.setItem(LOGS_KEY, "[]");
                      setLogs([]);
                    }}
                    className="text-xs text-slate-500 hover:text-rose-600 transition-colors"
                  >
                    Wyczyść logi
                  </button>
                </div>
                <div className="max-h-[500px] overflow-y-auto">
                  {logs.length === 0 ? (
                    <div className="p-8 text-center text-slate-400">
                      <Terminal className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p>Brak logów.</p>
                    </div>
                  ) : (
                    <div className="divide-y divide-slate-100">
                      {logs.map((log) => (
                        <div key={log.id} className="p-3 flex items-start gap-3 hover:bg-slate-50/50">
                          {log.level === "INFO" && <CheckCircle2 className="w-4 h-4 text-emerald-500 mt-0.5 shrink-0" />}
                          {log.level === "SUCCESS" && <CheckCircle2 className="w-4 h-4 text-blue-500 mt-0.5 shrink-0" />}
                          {log.level === "WARNING" && <AlertCircle className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />}
                          {log.level === "ERROR" && <XCircle className="w-4 h-4 text-rose-500 mt-0.5 shrink-0" />}
                          <div className="min-w-0">
                            <p className="text-sm text-slate-700">{log.message}</p>
                            <p className="text-xs text-slate-400 mt-0.5">
                              {new Date(log.created_at).toLocaleString("pl-PL")}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </Card>
            </motion.div>
          )}

          {activeTab === "config" && (
            <motion.div
              key="config"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-6"
            >
              <Card className="p-6">
                <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
                  <Globe className="w-5 h-5 text-slate-600" />
                  Konfiguracja bota
                </h2>
                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
                    <p className="text-sm font-medium text-slate-700 mb-1">Plik config.json</p>
                    <p className="text-xs text-slate-500 mb-3">
                      Bot odczytuje ustawienia z pliku <code className="bg-white px-1.5 py-0.5 rounded text-slate-700">config.json</code> w głównym folderze.
                    </p>
                    <pre className="text-xs bg-slate-800 text-slate-200 p-4 rounded-xl overflow-x-auto">
{`{
  "discord_token": "TWOJ_BOT_TOKEN",
  "discord_channel_id": 123456789,
  "szukana_fraza": "gogle",
  "min_cena_pln": 300,
  "maks_cena_pln": 2000,
  "interwal_sprawdzania_sek": 300
}`}
                    </pre>
                  </div>

                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-100">
                    <p className="text-sm font-medium text-slate-700 mb-1">Komendy Discord</p>
                    <p className="text-xs text-slate-500 mb-3">
                      Po uruchomieniu bota (<code className="bg-white px-1.5 py-0.5 rounded">python bot/bot.py</code>) dostępne są komendy:
                    </p>
                    <div className="space-y-2">
                      {[
                        ["!check [fraza] [min] [max]", "Ręczne sprawdzenie ofert"],
                        ["!status", "Status monitora i statystyki"],
                        ["!searches", "Lista wszystkich wyszukiwań"],
                        ["!add <fraza> <min> <max>", "Dodaj nowe wyszukiwanie"],
                        ["!remove <id>", "Usuń wyszukiwanie"],
                        ["!toggle <id>", "Włącz/wyłącz wyszukiwanie"],
                        ["!clear", "Wyczyść bazę seen_offers (reset)"],
                        ["!logs [limit]", "Pokaż ostatnie logi"],
                        ["!helpbot", "Pomoc"],
                      ].map(([cmd, desc]) => (
                        <div key={cmd} className="flex items-center gap-3 text-xs">
                          <code className="shrink-0 bg-emerald-50 text-emerald-700 px-2 py-1 rounded font-mono">{cmd}</code>
                          <span className="text-slate-600">{desc}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <button
                      onClick={handleClear}
                      className="flex items-center gap-2 px-4 py-2 rounded-xl bg-rose-50 text-rose-700 hover:bg-rose-100 text-sm font-medium transition-colors border border-rose-200"
                    >
                      <Trash2 className="w-4 h-4" />
                      Wyczyść seen_offers
                    </button>
                  </div>
                </div>
              </Card>

              <Card className="p-6">
                <h2 className="text-lg font-bold text-slate-800 mb-4">Instalacja</h2>
                <div className="space-y-3 text-sm text-slate-600">
                  <p>1. Zainstaluj zależności Python:</p>
                  <pre className="bg-slate-800 text-slate-200 p-3 rounded-xl text-xs overflow-x-auto">
                    pip install discord.py tls_client beautifulsoup4
                  </pre>
                  <p>2. Utwórz bota na Discord Developer Portal i skopiuj token.</p>
                  <p>3. Uzupełnij <code className="bg-slate-100 px-1 rounded">config.json</code> o token i ID kanału.</p>
                  <p>4. Uruchom bota:</p>
                  <pre className="bg-slate-800 text-slate-200 p-3 rounded-xl text-xs overflow-x-auto">
                    python bot/bot.py
                  </pre>
                </div>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}
