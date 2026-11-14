// Sostituisci qui i segnaposto con i nomi e i contributi reali del team.
// Per le foto personali, in futuro basta sostituire l'SVG dentro contact-avatar.
const teamMembers = [
  { number: "01", name: "Cortese Marco", role: "[Role / contribution to the project]" },
  { number: "02", name: "D'Agostino Mattia", role: "[Role / contribution to the project]" },
  { number: "03", name: "De Martini Matteo", role: "[Role / contribution to the project]" },
  { number: "04", name: "Pozzolini Gobbi Alessandro", role: "Frontend developer" },
  { number: "05", name: "Tesch Vittorio", role: "[Role / contribution to the project]" },
  { number: "06", name: "Valente Lorenzo", role: "Nitrogen Expert" },
];

export default function Contatti() {
  return (
    <main className="inner-page contacts-page">
      <div className="contacts-layout">
        <div className="contacts-heading">
          <span className="contacts-eyebrow">FIELDWISE / TEAM</span>
          <h1>Meet the team</h1>
          <p>The six people behind FIELDWISE and their contributions to the project.</p>
        </div>

        <div className="contacts-grid">
          {teamMembers.map((member, index) => (
            <article className={`contact-card contact-card--${index + 1}`} key={member.number}>
              <div className="contact-card-top">
                <div className="contact-avatar" aria-hidden="true">
                  <svg viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="60" cy="60" r="59" className="avatar-circle" />
                    <circle cx="60" cy="46" r="19" className="avatar-head" />
                    <path d="M21 106c2-24 17-39 39-39s37 15 39 39" className="avatar-shoulders" />
                    <path d="M34 40c2-14 12-23 26-23 16 0 26 11 26 25" className="avatar-hair" />
                    <path d="M23 32c-7 3-10 9-10 17m91 14c4-6 5-12 2-18" className="avatar-flourish" />
                  </svg>
                </div>
                <span className="contact-index">{member.number} / 06</span>
              </div>
              <div className="contact-card-body">
                <h2>{member.name}</h2>
                <div className="contact-card-divider" aria-hidden="true" />
                <span className="contact-role-title">CONTRIBUTIONS</span>
                <p className="contact-role">{member.role}</p>
              </div>
            </article>
          ))}
        </div>
      </div>
    </main>
  );
}
