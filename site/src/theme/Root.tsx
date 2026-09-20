import React, { useEffect } from 'react';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';

declare global {
  class PagefindHighlight {
    constructor(options: { highlightParam: string });
  }
}

export default function Root({ children }: { children: React.ReactNode }): React.ReactElement {
  const { i18n, siteConfig } = useDocusaurusContext();
  const { currentLocale, defaultLocale } = i18n;
  const siteBaseUrl = siteConfig.baseUrl.endsWith(`/${currentLocale}/`) ? siteConfig.baseUrl.slice(0, -currentLocale.length - 1) : siteConfig.baseUrl;
  const highlightPath = `${siteBaseUrl}${currentLocale === defaultLocale ? '' : `${currentLocale}/`}pagefind/pagefind-highlight.js`;

  useEffect(() => {
    // Runtime selection is required: Pagefind's highlight script is emitted per locale.
    void import(/* webpackIgnore: true */ highlightPath).then(() => new PagefindHighlight({ highlightParam: 'pagefind-highlight' })).catch(() => undefined);
  }, [highlightPath]);

  return <>{children}</>;
}
