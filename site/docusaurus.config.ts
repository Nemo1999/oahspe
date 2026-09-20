import type { Config } from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import type { PluginOptions as PwaPluginOptions } from '@docusaurus/plugin-pwa';
import { themes as prismThemes } from 'prism-react-renderer';

const config: Config = {
  title: 'Oahspe',
  tagline: 'A Kosmon Bible in the Words of Jehovih and His Angel Embassadors',
  favicon: 'img/favicon.ico',

  url: 'https://nemo1999.github.io',
  baseUrl: '/oahspe/',

  organizationName: 'Nemo1999',
  projectName: 'oahspe',
  deploymentBranch: 'gh-pages',
  trailingSlash: false,

  onBrokenLinks: 'warn',
  markdown: { hooks: { onBrokenMarkdownLinks: 'warn' } },

  i18n: {
    defaultLocale: 'en',
    locales: ['en', 'zh-hant', 'zh-hans', 'ja'],
    localeConfigs: {
      en: {
        label: 'English',
        direction: 'ltr',
        htmlLang: 'en',
      },
      'zh-hant': {
        label: '繁體中文',
        direction: 'ltr',
        htmlLang: 'zh-Hant',
      },
      'zh-hans': {
        label: '简体中文',
        direction: 'ltr',
        htmlLang: 'zh-Hans',
      },
      ja: {
        label: '日本語',
        direction: 'ltr',
        htmlLang: 'ja',
      },
    },
  },

  presets: [
    [
      'classic',
      {
        docs: {
          routeBasePath: '/',
          sidebarPath: './sidebars.ts',
          editUrl: undefined,
          showLastUpdateTime: false,
          breadcrumbs: true,
        },
        blog: {
          showReadingTime: true,
          path: '../blog',
          blogTitle: 'Oahspe Notes',
          blogDescription: 'Commentary, translations and scholarly notes on Oahspe',
          postsPerPage: 10,
        },
        theme: {
          customCss: './src/css/custom.css',
        },
        sitemap: {
          changefreq: 'weekly',
          priority: 0.5,
        },
      } satisfies Preset.Options,
    ],
  ],

  plugins: [
    [
      '@docusaurus/plugin-pwa',
      {
        debug: false,
        offlineModeActivationStrategies: [
          'appInstalled',
          'standalone',
          'queryString',
        ],
        pwaHead: [
          { tagName: 'link', rel: 'manifest', href: '/oahspe/manifest.json' },
          { tagName: 'meta', name: 'theme-color', content: '#1a1a2e' },
          { tagName: 'meta', name: 'apple-mobile-web-app-capable', content: 'yes' },
          { tagName: 'meta', name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent' },
          { tagName: 'link', rel: 'apple-touch-icon', href: '/oahspe/img/icon-192.png' },
        ],
        swCustom: require.resolve('./swCustom.js'),
        injectManifestConfig: {
          globPatterns: ['**/*.{js,jsx,ts,tsx,css,json,html,woff2}'],
        },
      } as PwaPluginOptions,
    ],
  ],

  themeConfig: {
    image: 'img/oahspe-social.png',

    colorMode: {
      defaultMode: 'dark',
      disableSwitch: false,
      respectPrefersColorScheme: true,
    },

    navbar: {
      title: 'Oahspe',
      logo: {
        alt: 'Oahspe emblem',
        src: 'img/logo.png',
        srcDark: 'img/logo-dark.png',
      },
      items: [
        {
          label: 'Books',
          to: '/',
          position: 'left',
        },
        { to: '/glossary', label: 'Glossary', position: 'left' },
        { to: '/bookmarks', label: 'Bookmarks', position: 'left' },
        { to: '/blog', label: 'Notes', position: 'left' },
        {
          type: 'search',
          position: 'right',
        },
        // Locale dropdown removed: the in-page verse toolbox controls reading language
        // (navbar dropdown had no effect on the reader). Reading language persists via localStorage.
        {
          href: 'https://github.com/Nemo1999/oahspe',
          label: 'GitHub',
          position: 'right',
        },
      ],
      hideOnScroll: true,
    },

    footer: {
      style: 'dark',
      links: [
        {
          title: 'Text',
          items: [
            { label: 'Read Online', to: '/' },
            { label: 'Glossary', to: '/glossary' },
            { label: 'Bookmarks', to: '/bookmarks' },
            { label: 'Notes', to: '/blog' },
          ],
        },
        {
          title: 'Community',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/Nemo1999/oahspe',
            },
          ],
        },
      ],
      copyright: `Oahspe is public domain (first published 1882). Site content and tooling © ${new Date().getFullYear()} contributors.`,
    },

    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },

    docs: {
      sidebar: {
        hideable: true,
        autoCollapseCategories: true,
      },
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
