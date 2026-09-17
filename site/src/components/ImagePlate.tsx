import React, { useState, useEffect, useCallback } from 'react';

interface ImagePlateProps {
  plateId: number;
  caption?: string;
}

export default function ImagePlate({ plateId, caption }: ImagePlateProps): React.ReactElement {
  const [open, setOpen]     = useState(false);
  const [loaded, setLoaded] = useState(false);

  const handleClose = useCallback(() => {
    setOpen(false);
    setLoaded(false);
  }, []);

  // Keyboard close
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, handleClose]);

  // Lock body scroll when lightbox is open
  useEffect(() => {
    if (typeof document === 'undefined') return; // SSR guard
    document.body.style.overflow = open ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [open]);

  const padId   = String(plateId).padStart(3, '0');
  const thumbSrc = `/oahspe/static/plates/thumbs/plate-${padId}-thumb.jpg`;
  const fullSrc  = `/oahspe/static/plates/full/plate-${padId}.jpg`;
  const altText  = caption ?? `Oahspe Plate ${plateId}`;

  return (
    <>
      <figure className="image-plate">
        <button
          className="image-plate-thumb-btn"
          onClick={() => setOpen(true)}
          aria-label={`View full-size: ${altText}`}
        >
          <img
            src={thumbSrc}
            alt={altText}
            loading="lazy"
            className="image-plate-thumb"
          />
        </button>
        {caption && (
          <figcaption className="image-plate-caption">{caption}</figcaption>
        )}
      </figure>

      {open && (
        <div
          className="image-plate-overlay"
          onClick={handleClose}
          role="dialog"
          aria-modal="true"
          aria-label={altText}
        >
          <div
            className="image-plate-lightbox"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="image-plate-close"
              onClick={handleClose}
              aria-label="Close"
            >
              ✕
            </button>
            {!loaded && (
              <div className="image-plate-loading" aria-live="polite">
                Loading…
              </div>
            )}
            <img
              src={fullSrc}
              alt={altText}
              className="image-plate-full"
              style={{ display: loaded ? 'block' : 'none' }}
              onLoad={() => setLoaded(true)}
            />
            {caption && (
              <p className="image-plate-caption image-plate-caption--modal">
                {caption}
              </p>
            )}
          </div>
        </div>
      )}
    </>
  );
}
