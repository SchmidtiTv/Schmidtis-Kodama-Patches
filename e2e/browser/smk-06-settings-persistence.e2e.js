const assert = require("node:assert/strict");

const { startWithProfile } = require("./smoke-support.cjs");

describe("SMK-06 settings persistence", () => {
  beforeEach(() => startWithProfile("local"));

  it("persists language and theme through a relaunch-style reload", async () => {
    await $("[data-testid='account-menu-trigger']").click();
    await $("[data-testid='menu-settings']").click();
    await $("[data-testid='settings-nav-language']").click();
    await $("[data-testid='settings-language-en']").click();
    await $("[data-testid='settings-nav-darstellung']").click();
    await $("[data-testid='theme-light']").click();

    await browser.waitUntil(async () =>
      browser.execute(
        () =>
          localStorage.getItem("kiyoshi-lang") === "en" &&
          localStorage.getItem("kiyoshi-theme") === "light"
      )
    );
    await browser.refresh();
    await $("[data-testid='view-home']").waitForDisplayed();

    assert.equal(await $("html").getAttribute("data-theme"), "light");
    assert.equal(await browser.execute(() => localStorage.getItem("kiyoshi-lang")), "en");
    assert.equal(await $("[data-testid='nav-home']").getText(), "Home");
  });

  it("uses dark HeroUI tokens for OLED and restores light tokens when switching back", async () => {
    await $("[data-testid='account-menu-trigger']").click();
    await $("[data-testid='menu-settings']").click();
    await $("[data-testid='settings-nav-darstellung']").click();
    await $("[data-testid='theme-oled']").click();
    assert.equal(
      await browser.execute(() => document.documentElement.classList.contains("dark")),
      true
    );
    await browser.refresh();
    await $("[data-testid='view-home']").waitForDisplayed();
    assert.equal(await $("html").getAttribute("data-theme"), "oled");
    assert.equal(
      await browser.execute(() => document.documentElement.classList.contains("dark")),
      true
    );
    await $("[data-testid='account-menu-trigger']").click();
    await $("[data-testid='menu-settings']").click();
    await $("[data-testid='settings-nav-darstellung']").click();
    await $("[data-testid='theme-light']").click();
    assert.equal(
      await browser.execute(() => document.documentElement.classList.contains("dark")),
      false
    );
  });

  it("persists the Speed Dial setting and removes quick picks from Home", async () => {
    await $("[data-testid='view-home'] [data-track-id='track-normal']").waitForDisplayed();
    await $("[data-testid='account-menu-trigger']").click();
    await $("[data-testid='menu-settings']").click();
    await $("[data-testid='settings-nav-darstellung']").click();
    const toggle = await $("[role='switch'][aria-label='Speed Dial']");
    await toggle.scrollIntoView();
    await toggle.click();
    await browser.waitUntil(() =>
      browser.execute(() => localStorage.getItem("kodama-speed-dial") === "false")
    );
    await browser.refresh();
    await $("[data-testid='view-home']").waitForDisplayed();
    await browser.waitUntil(() =>
      browser.execute(
        () => !document.querySelector("[data-testid='view-home'] [data-track-id='track-normal']")
      )
    );
    assert.equal(await browser.execute(() => localStorage.getItem("kodama-speed-dial")), "false");
    await $("[data-testid='account-menu-trigger']").click();
    await $("[data-testid='menu-settings']").click();
    await $("[data-testid='settings-nav-darstellung']").click();
    const restoredToggle = await $("[role='switch'][aria-label='Speed Dial']");
    await restoredToggle.scrollIntoView();
    await restoredToggle.click();
    await browser.refresh();
    await $("[data-testid='view-home'] [data-track-id='track-normal']").waitForDisplayed();
  });

  it("shows English equalizer controls with matching settings-card corners", async () => {
    await $("[data-testid='account-menu-trigger']").click();
    await $("[data-testid='menu-settings']").click();
    await $("[data-testid='settings-nav-wiedergabe']").click();
    const toggle = await $("[role='switch'][aria-label='Equalizer']");
    await toggle.scrollIntoView();
    await toggle.click();
    const controls = await $("[data-testid='equalizer-controls']");
    await controls.waitForDisplayed();
    assert.ok((await controls.getText()).includes("Preamp"));
    const cards = await browser.execute(() => {
      const header = document
        .querySelector("[role='switch'][aria-label='Equalizer']")
        .closest(".card");
      const panel = document.querySelector("[data-testid='equalizer-controls']");
      return {
        headerText: header.textContent,
        headerRadius: getComputedStyle(header).borderTopLeftRadius,
        panelRadius: getComputedStyle(panel).borderTopLeftRadius,
      };
    });
    assert.ok(cards.headerText.includes("Ten frequency bands and a preamp, applied to playback."));
    assert.equal(cards.panelRadius, cards.headerRadius);
    assert.notEqual(cards.panelRadius, "0px");
  });

  it("customizes the player bar from Appearance settings", async () => {
    await $("[data-testid='account-menu-trigger']").click();
    await $("[data-testid='menu-settings']").click();
    await $("[data-testid='settings-nav-darstellung']").click();

    const customizer = await $("[data-testid='player-bar-customizer']");
    await customizer.scrollIntoView();
    await customizer.waitForDisplayed();

    await $("[data-testid='player-bar-remove-queue']").click();
    await browser.waitUntil(async () =>
      browser.execute(() => !JSON.parse(localStorage.getItem("kiyoshi-player-bar-controls")).queue)
    );

    await $("[data-testid='player-bar-add-control']").click();
    await $("[data-testid='player-bar-add-queue']").click();
    await browser.waitUntil(async () =>
      browser.execute(() => JSON.parse(localStorage.getItem("kiyoshi-player-bar-controls")).queue)
    );
  });
});
