import { createGlobalStyle } from "antd-style";
import { ConfigProvider, theme as antdTheme } from "antd";
import zhCN from "antd/locale/zh_CN";
import enUS from "antd/locale/en_US";
import dayjs from "dayjs";
import "dayjs/locale/zh-cn";
import { useEffect } from "react";
import DesktopWindowControls from "./components/DesktopWindowControls";
import {
  DesktopChromeProvider,
  useDesktopChrome,
} from "./hooks/useDesktopChrome";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { useTranslation } from "react-i18next";
import MainLayout from "./layouts/MainLayout";
import LoginPage from "./pages/Login";
import OidcComplete from "./pages/Login/OidcComplete";
import SetupPage from "./pages/Setup";
import InvitePage from "./pages/Invite";
import AuthGuard from "./components/AuthGuard";
import OctopSpinner from "./components/OctopSpinner";
import { AntdAppProvider } from "./components/AntdAppProvider";
import GlobalErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider, useTheme } from "./context/ThemeContext";
import { AgentProvider } from "./context/AgentContext";
import { LayoutModeProvider } from "./context/LayoutModeContext";
import { VoiceOutputProvider } from "./context/VoiceOutputContext";
import { useIsMobile } from "./hooks/useIsMobile";
import { useUnauthorizedRedirect } from "./hooks/useUnauthorizedRedirect";
import { installDesktopExternalLinks } from "./utils/desktopExternalLinks";
import { brandTokensFor } from "./styles/themePalettes";
import "./styles/theme-vars.css";
import "./styles/layout.css";
import "./styles/form-override.css";
import "./styles/spin-override.css";

const GlobalStyle = createGlobalStyle`
* {
  margin: 0;
  box-sizing: border-box;
}
`;

function ThemedApp() {
  const { isDark, palette, customColor } = useTheme();
  const { t, i18n } = useTranslation();
  const isMobile = useIsMobile();
  const desktopChrome = useDesktopChrome();
  const brandTokens = brandTokensFor(palette, isDark, customColor);
  // The Starbucks palette themes the shell surfaces (cream / espresso green).
  // Keep antd portals (modal, select, table…) on the same tint in dark mode.
  const isStarbucks = palette === "starbucks";
  // Make antd built-ins (Popconfirm OK/Cancel, Modal default footer, Empty,
  // Pagination, DatePicker, Table… ) follow the current UI language.
  // DatePicker month/weekday labels come from dayjs — keep it in sync too.
  const isZh = i18n.language?.toLowerCase().startsWith("zh") ?? false;
  const antdLocale = isZh ? zhCN : enUS;
  dayjs.locale(isZh ? "zh-cn" : "en");

  useUnauthorizedRedirect();

  useEffect(() => installDesktopExternalLinks(), []);

  // Set document title based on current language
  useEffect(() => {
    document.title = t("app.pageTitle");
  }, [t]);

  const themeConfig = {
    algorithm: isDark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    token: {
      borderRadius: 10,
      ...(isMobile
        ? {
            fontSize: 15,
            fontSizeSM: 13,
            fontSizeLG: 17,
            fontSizeXL: 22,
            controlHeight: 36,
          }
        : {}),
      ...(isDark
        ? {
            colorBgBase: isStarbucks ? "#121d19" : "#0f1117",
            colorTextBase: isStarbucks ? "#f2efe6" : "#e7e7ed",
            colorBgContainer: isStarbucks ? "#121d19" : "#0f1117",
            colorBgElevated: isStarbucks ? "#1b2922" : "#1a1c28",
            colorBgLayout: isStarbucks ? "#0c1512" : "#0b0d14",
            colorBgSpotlight: "rgba(0, 0, 0, 0.85)",
            colorBgMask: "rgba(5, 5, 8, 0.80)",
            colorBorder: isStarbucks
              ? "rgba(242,239,230,0.10)"
              : "rgba(255,255,255,0.08)",
            colorBorderSecondary: isStarbucks
              ? "rgba(242,239,230,0.06)"
              : "rgba(255,255,255,0.05)",
            colorText: isStarbucks
              ? "rgba(242, 239, 230, 0.92)"
              : "rgba(255, 255, 255, 0.92)",
            colorTextSecondary: isStarbucks
              ? "rgba(242, 239, 230, 0.64)"
              : "rgba(255, 255, 255, 0.64)",
            colorTextTertiary: isStarbucks
              ? "rgba(242, 239, 230, 0.38)"
              : "rgba(255, 255, 255, 0.38)",
            colorTextQuaternary: isStarbucks
              ? "rgba(242, 239, 230, 0.22)"
              : "rgba(255, 255, 255, 0.22)",
            colorFill: isStarbucks
              ? "rgba(242, 239, 230, 0.06)"
              : "rgba(255, 255, 255, 0.06)",
            colorFillSecondary: isStarbucks
              ? "rgba(242, 239, 230, 0.04)"
              : "rgba(255, 255, 255, 0.04)",
            colorFillTertiary: isStarbucks
              ? "rgba(242, 239, 230, 0.03)"
              : "rgba(255, 255, 255, 0.03)",
            colorFillQuaternary: isStarbucks
              ? "rgba(242, 239, 230, 0.02)"
              : "rgba(255, 255, 255, 0.02)",
            colorBgTextHover: isStarbucks
              ? "rgba(242, 239, 230, 0.06)"
              : "rgba(255, 255, 255, 0.06)",
            ...brandTokens,
            boxShadow: "0px 4px 6px 0px rgba(0, 0, 0, 0.3)",
            boxShadowSecondary:
              "0px 12px 24px -16px rgba(0, 0, 0, 0.2), 0px 8px 40px 0px rgba(0, 0, 0, 0.3)",
          }
        : {
            ...brandTokens,
          }),
    },
    components: isDark
      ? {
          Modal: {
            headerBg: isStarbucks ? "#1b2922" : "#1a1c28",
            contentBg: isStarbucks ? "#1b2922" : "#1a1c28",
          },
          Input: { colorBgBase: isStarbucks ? "#121d19" : "#0f1117" },
          InputNumber: { colorBgBase: isStarbucks ? "#121d19" : "#0f1117" },
          Select: {
            colorBgBase: isStarbucks ? "#121d19" : "#0f1117",
            selectorBg: isStarbucks ? "#121d19" : "#0f1117",
          },
          DatePicker: { colorBgBase: isStarbucks ? "#121d19" : "#0f1117" },
          Segmented: { itemSelectedBg: isStarbucks ? "#1b2922" : "#1a1c28" },
          Card: { colorBgContainer: isStarbucks ? "#18251f" : "#161822" },
          Tooltip: {
            colorBgSpotlight: isStarbucks ? "#273830" : "#424242",
          },
        }
      : {},
  };

  return (
    <ConfigProvider
      theme={themeConfig}
      prefixCls="octop"
      locale={antdLocale}
      spin={{ indicator: <OctopSpinner /> }}
    >
      <AntdAppProvider>
        <DesktopChromeProvider value={desktopChrome}>
          {desktopChrome ? (
            <DesktopWindowControls chrome={desktopChrome} />
          ) : null}
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/login/oidc/complete" element={<OidcComplete />} />
            <Route path="/setup" element={<SetupPage />} />
            <Route path="/invite" element={<InvitePage />} />
            <Route
              path="/*"
              element={
                <AuthGuard>
                  <AgentProvider>
                    <LayoutModeProvider>
                      <VoiceOutputProvider>
                        <MainLayout />
                      </VoiceOutputProvider>
                    </LayoutModeProvider>
                  </AgentProvider>
                </AuthGuard>
              }
            />
          </Routes>
        </DesktopChromeProvider>
      </AntdAppProvider>
    </ConfigProvider>
  );
}

function App() {
  return (
    // `useTransitions` off: with router transitions on, React keeps the old
    // page mounted while a lazy route chunk downloads and never renders the
    // Suspense fallback, so a nav click looks like it did nothing.
    <BrowserRouter useTransitions={false}>
      <GlobalErrorBoundary>
        <GlobalStyle />
        <ThemeProvider>
          <ThemedApp />
        </ThemeProvider>
      </GlobalErrorBoundary>
    </BrowserRouter>
  );
}

export default App;
