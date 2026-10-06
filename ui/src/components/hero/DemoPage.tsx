import { memo } from 'react';
import type { Variant } from '../../lib/sweep';
import './demo.css';

/**
 * An original demo page ("Tessel", a made-up product) used only by the hero sweep. It reflows with CSS container
 * queries on its frame, so it genuinely changes layout as the frame's width changes. Elements marked `data-m` are
 * measured live (lib/sweep.measureLayout); `data-g` names groups that must not overlap.
 *
 * variant="before" ships a deliberate bug: from 1080 px the pricing goes three-up with 346 px minimum cards; the last card ends at
 * 1134 px, so the page overflows between 1080 and 1133 px. variant="after" uses minmax(0, 1fr) and fits everywhere.
 */
export const DemoPage = memo(function DemoPage({ variant }: { variant: Variant }) {
  return (
    <div className="dm" data-variant={variant} aria-hidden="true">
      <nav className="dm-nav">
        <span className="dm-brand" data-m="brand" data-g="nav">
          <span className="dm-logo" />
          Tessel
        </span>
        <ul className="dm-links" data-m="links" data-g="nav">
          <li>Product</li>
          <li>Pricing</li>
          <li>Docs</li>
          <li>Changelog</li>
        </ul>
        <span className="dm-btn dm-btn-sm" data-m="nav-cta" data-g="nav">
          Start free
        </span>
      </nav>

      <header className="dm-hero">
        <div className="dm-copy" data-m="copy" data-g="hero">
          <p className="dm-kicker">New · Boards 2.0</p>
          <h3 className="dm-h">Plans your whole team can read.</h3>
          <p className="dm-p">Roadmaps, notes and decisions in one calm board. Share a link; everyone sees the same thing.</p>
          <div className="dm-ctas">
            <span className="dm-btn" data-m="cta-1" data-g="ctas">
              Start free
            </span>
            <span className="dm-btn dm-btn-ghost" data-m="cta-2" data-g="ctas">
              Book a demo
            </span>
          </div>
        </div>
        <div className="dm-art" data-m="art" data-g="hero">
          <div className="dm-board">
            {[0, 1, 2].map((c) => (
              <div key={c} className="dm-col">
                <span className="dm-col-h" />
                {Array.from({ length: 3 - (c % 2) }, (_, i) => (
                  <span key={i} className={`dm-card dm-card-${(c + i) % 3}`} />
                ))}
              </div>
            ))}
          </div>
        </div>
      </header>

      <section className="dm-stats">
        {[
          ['4.9', 'average rating'],
          ['12k', 'teams'],
          ['99.98%', 'uptime'],
        ].map(([n, l]) => (
          <div key={l} className="dm-stat">
            <b>{n}</b>
            <span>{l}</span>
          </div>
        ))}
      </section>

      <section className="dm-pricing" data-m="pricing">
        {[
          ['Starter', '$0', ['3 boards', 'Unlimited viewers', 'Email support']],
          ['Team', '$12', ['Unlimited boards', 'Comments + mentions', 'Version history']],
          ['Studio', '$29', ['Everything in Team', 'SSO + audit log', 'Priority support']],
        ].map(([name, price, feats], i) => (
          <div key={name as string} className={`dm-plan ${i === 1 ? 'dm-plan-hi' : ''}`} data-m={`plan-${i}`} data-g="plans">
            <p className="dm-plan-name">{name}</p>
            <p className="dm-price">
              <b>{price}</b> / seat / mo
            </p>
            <ul>
              {(feats as string[]).map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
            <span className={`dm-btn ${i === 1 ? '' : 'dm-btn-ghost'}`}>Choose {name}</span>
          </div>
        ))}
      </section>
    </div>
  );
});
