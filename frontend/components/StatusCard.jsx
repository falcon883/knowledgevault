function StatusCard({ label, status }) {
  return (
    <div
      style={{
        display: 'inline-block',
        padding: '0.9rem 1.2rem',
        border: '1px solid #dfe3e8',
        borderRadius: '12px',
        background: '#f8fafc',
        marginTop: '1rem',
      }}
    >
      <div style={{ fontSize: '0.8rem', color: '#5f6b7a', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
        {label}
      </div>
      <div style={{ fontSize: '1.1rem', fontWeight: 700, marginTop: '0.2rem' }}>{status}</div>
    </div>
  );
}

export default StatusCard;
