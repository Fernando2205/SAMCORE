interface Props {
  tamano?: number
  sobreTinta?: boolean
}

export function Sello ({ tamano = 32, sobreTinta = false }: Props) {
  const exterior = sobreTinta ? '#faf7f1' : '#16181a'
  const acento = sobreTinta ? '#2e9d8a' : '#0c7a6b'
  return (
    <svg width={tamano} height={tamano} viewBox='0 0 48 48' fill='none' aria-hidden='true'>
      <circle cx='24' cy='24' r='21' stroke={exterior} strokeWidth='2.5' />
      <circle cx='24' cy='24' r='14' stroke={acento} strokeWidth='2' strokeDasharray='6 5' />
      <circle cx='24' cy='24' r='5.5' fill={acento} />
    </svg>
  )
}

export function Wordmark ({ clase = 'text-2xl' }: { clase?: string }) {
  return (
    <span className={`font-serif ${clase}`}>
      <span className='text-marca'>Sam</span>Core
    </span>
  )
}
