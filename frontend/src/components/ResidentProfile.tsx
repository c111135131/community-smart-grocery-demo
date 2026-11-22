import type { Resident } from "../api/types";
import { allergyLabel, preferenceLabel } from "../labels";

interface Props {
  resident: Resident;
  onLogout: () => void;
}

export default function ResidentProfile({ resident, onLogout }: Props) {
  const { dietary_preferences: prefs, allergies, notes } = resident.health_profile;
  return (
    <section className="panel" aria-labelledby="profile-title">
      <div className="panel-head">
        <h2 id="profile-title">{resident.display_name}</h2>
        <button type="button" className="secondary" onClick={onLogout}>
          登出
        </button>
      </div>
      <dl className="kv">
        <div>
          <dt>飲食偏好</dt>
          <dd>
            {prefs.length === 0 ? (
              <span className="muted">未設定</span>
            ) : (
              prefs.map((p) => <span key={p} className="tag">{preferenceLabel(p)}</span>)
            )}
          </dd>
        </div>
        <div>
          <dt>過敏原</dt>
          <dd>
            {allergies.length === 0 ? (
              <span className="muted">無</span>
            ) : (
              allergies.map((a) => <span key={a} className="tag warn">{allergyLabel(a)}</span>)
            )}
          </dd>
        </div>
        {notes && (
          <div>
            <dt>備註</dt>
            <dd>{notes}</dd>
          </div>
        )}
      </dl>
    </section>
  );
}
