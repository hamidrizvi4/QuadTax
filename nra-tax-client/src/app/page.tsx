import Link from "next/link";
import { ArrowRight, ShieldCheck, Zap, Globe } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="flex flex-col min-h-screen bg-slate-50">
      {/* Hero Section */}
      <main className="flex-1 flex flex-col items-center justify-center p-6 text-center">
        <div className="w-20 h-20 bg-blue-600 rounded-2xl flex items-center justify-center mb-8 shadow-xl shadow-blue-200">
          <ShieldCheck className="w-12 h-12 text-white" />
        </div>
        
        <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight mb-4 sm:text-5xl">
          NRA <span className="text-blue-600">Tax Engine</span>
        </h1>
        
        <p className="text-lg text-slate-600 max-w-md mb-10 leading-relaxed">
          The fastest way for international students on F-1 and J-1 visas to file their US tax returns with AI precision.
        </p>

        <Link 
          href="/intake/eligibility"
          className="group flex items-center gap-3 bg-slate-900 hover:bg-slate-800 text-white px-8 py-4 rounded-full text-lg font-semibold transition-all shadow-lg active:scale-95"
        >
          Start My Tax Return
          <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
        </Link>
      </main>

      {/* Feature Grid */}
      <section className="grid grid-cols-1 sm:grid-cols-3 gap-8 p-8 max-w-5xl mx-auto w-full mb-12">
        <div className="flex flex-col items-center text-center">
          <div className="w-12 h-12 bg-white rounded-xl flex items-center justify-center shadow-md mb-4">
            <Zap className="w-6 h-6 text-yellow-500" />
          </div>
          <p className="font-bold text-slate-800">Instant Processing</p>
          <p className="text-sm text-slate-500">OCR converts scans to data in seconds</p>
        </div>
        
        <div className="flex flex-col items-center text-center">
          <div className="w-12 h-12 bg-white rounded-xl flex items-center justify-center shadow-md mb-4">
            <Globe className="w-6 h-6 text-blue-500" />
          </div>
          <p className="font-bold text-slate-800">Treaty Optimized</p>
          <p className="text-sm text-slate-500">Maximum refunds from global tax treaties</p>
        </div>

        <div className="flex flex-col items-center text-center">
          <div className="w-12 h-12 bg-white rounded-xl flex items-center justify-center shadow-md mb-4">
            <ShieldCheck className="w-6 h-6 text-green-500" />
          </div>
          <p className="font-bold text-slate-800">100% Audit Proof</p>
          <p className="text-sm text-slate-500">Deterministic math based on IRS rules</p>
        </div>
      </section>

      {/* Footer */}
      <footer className="p-6 text-center text-slate-400 text-xs border-t border-slate-200">
        © {new Date().getFullYear()} NRA Tax Engine. Built for Sprintax Hybrid.
      </footer>
    </div>
  );
}
