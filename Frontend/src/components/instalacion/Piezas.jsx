// Piezas compartidas por los pasos del asistente. Viven aquí y no dentro
// de cada paso para que los siete se vean iguales: un formulario que
// cambia de aspecto a mitad de una instalación parece roto.

import { AlertTriangle, Check, Info, Loader2, X } from 'lucide-react'

export function Marco({ paso, total, children, ancho = 'max-w-3xl' }) {
  return (
    <div
      className="min-h-screen bg-[#0a0a0a] flex items-center justify-center p-4"
      style={{ backgroundImage: 'linear-gradient(45deg, #0a0a0a 25%, #1a1a1a 100%)' }}
    >
      <div className={`w-full ${ancho}`}>
        <div className="bg-[#141414] border border-red-600/30 rounded-xl p-8 sm:p-10
                        shadow-[0_0_50px_rgba(220,38,38,0.15)]">
          <div className="text-center mb-6">
            <img src="/Logo.png" alt="Race Core Studio" className="w-56 mx-auto object-contain" />
            <p className="text-[11px] text-neutral-500 tracking-[0.22em] font-bold mt-2">
              ASISTENTE DE INSTALACIÓN
            </p>
          </div>

          <Progreso paso={paso} total={total} />
          {children}
        </div>
      </div>
    </div>
  )
}

function Progreso({ paso, total }) {
  if (!paso) return null

  return (
    <>
      <div className="flex gap-1.5 mb-1">
        {Array.from({ length: total }, (_, i) => (
          <div
            key={i}
            className={`flex-1 h-1 rounded-full transition-colors ${
              i + 1 < paso ? 'bg-neutral-700'
                : i + 1 === paso ? 'bg-red-600'
                : 'bg-neutral-800'
            }`}
          />
        ))}
      </div>
      <p className="text-[11px] text-neutral-500 font-bold tracking-wider text-right mb-6">
        PASO {paso} DE {total}
      </p>
    </>
  )
}

export function Titulo({ children, sub }) {
  return (
    <>
      <h2 className="text-2xl font-black italic text-white mb-2">{children}</h2>
      {sub && <p className="text-neutral-400 text-sm leading-relaxed mb-6">{sub}</p>}
    </>
  )
}

export function Campo({ etiqueta, ayuda, children }) {
  return (
    <div className="mb-4">
      {etiqueta && (
        <label className="block text-[11px] text-neutral-400 font-bold tracking-wider mb-1.5">
          {etiqueta}
        </label>
      )}
      {children}
      {ayuda && <p className="text-xs text-neutral-500 mt-1.5 leading-relaxed">{ayuda}</p>}
    </div>
  )
}

export function Entrada({ estado, className = '', ...props }) {
  const borde = estado === 'ok' ? 'border-green-600'
              : estado === 'error' ? 'border-red-600'
              : 'border-neutral-700 focus:border-red-600'

  return (
    <input
      {...props}
      className={`w-full bg-[#1c1c1f] border ${borde} rounded-lg px-3.5 py-2.5
                  text-neutral-200 text-[15px] outline-none transition-colors
                  placeholder:text-neutral-600 ${className}`}
    />
  )
}

const AVISOS = {
  ok:    { Icon: Check,         clase: 'bg-green-600/10 border-green-600 text-green-300' },
  error: { Icon: X,             clase: 'bg-red-600/10 border-red-600 text-red-300' },
  aviso: { Icon: AlertTriangle, clase: 'bg-amber-600/10 border-amber-600 text-amber-300' },
  info:  { Icon: Info,          clase: 'bg-blue-600/10 border-blue-600 text-blue-300' },
}

export function Aviso({ tipo = 'info', titulo, children }) {
  const { Icon, clase } = AVISOS[tipo] || AVISOS.info

  return (
    <div className={`border-l-4 rounded-lg px-4 py-3 mb-4 ${clase}`}>
      <div className="flex gap-2.5">
        <Icon size={17} className="shrink-0 mt-0.5" />
        <div className="min-w-0">
          {titulo && <p className="font-bold text-sm">{titulo}</p>}
          {children && (
            <div className="text-neutral-400 text-sm mt-0.5 leading-relaxed break-words">
              {children}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export function Pie({ children }) {
  return <div className="flex gap-3 items-center mt-7">{children}</div>
}

export function Boton({ children, cargando, variante = 'primario', ...props }) {
  const estilos = {
    primario:   'bg-red-600 hover:bg-red-700 text-white',
    verde:      'bg-green-600 hover:bg-green-700 text-white',
    secundario: 'bg-transparent border border-neutral-700 text-neutral-400 hover:text-neutral-200',
    terciario:  'bg-neutral-800 border border-neutral-600 text-neutral-200 hover:bg-neutral-700',
  }[variante]

  return (
    <button
      {...props}
      disabled={props.disabled || cargando}
      className={`${estilos} rounded-lg px-6 py-3 text-[15px] font-bold transition-colors
                  disabled:opacity-50 disabled:cursor-not-allowed
                  flex items-center justify-center gap-2`}
    >
      {cargando && <Loader2 size={16} className="animate-spin" />}
      {children}
    </button>
  )
}

export const Espacio = () => <div className="flex-1" />

export function Mono({ children }) {
  return (
    <code className="bg-black/60 px-1.5 py-0.5 rounded text-[13px] text-neutral-300">
      {children}
    </code>
  )
}
