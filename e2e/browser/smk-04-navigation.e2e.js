const assert = require("node:assert/strict");

const { requests } = require("../fixtures/client.cjs");
const { startWithProfile } = require("./smoke-support.cjs");

describe("SMK-04 navigation", () => {
  beforeEach(() => startWithProfile("local"));

  it("opens every primary view and follows the active navigation state", async () => {
    const views = [
      ["home", "view-home"],
      ["library", "view-library"],
      ["liked", "view-liked"],
      ["history", "view-history"],
      ["downloads", "view-downloads"],
    ];

    for (const [nav, view] of views) {
      const navItem = await $(`[data-testid='nav-${nav}']`);
      await navItem.click();
      await $(`[data-testid='${view}']`).waitForDisplayed();
      assert.match(await navItem.getAttribute("class"), /bg-accent-dim/);
    }

    await $("[data-testid='nav-library']").click();
    const playlist = await $("[data-card-id='playlist-fixture']");
    await playlist.waitForDisplayed();
    await playlist.click();
    await $("//*[contains(., 'Fixture Playlist')]").waitForDisplayed();
  });

  it("keeps Home recommendations cached when returning from the library", async () => {
    const initialHome = await $("[data-testid='view-home']");
    await $("//*[contains(., 'Fixture Sunrise')]").waitForDisplayed();
    const requestsBeforeNavigation = await requests();
    const initialHomeRequests = requestsBeforeNavigation.filter(
      (request) => request.pathname === "/home"
    ).length;

    await $("[data-testid='nav-library']").click();
    await $("[data-testid='view-library']").waitForDisplayed();
    await $("[data-testid='nav-home']").click();
    const returnedHome = await $("[data-testid='view-home']");
    await returnedHome.waitForDisplayed();
    await $("//*[contains(., 'Fixture Sunrise')]").waitForDisplayed();

    assert.equal(returnedHome.elementId, initialHome.elementId);

    const requestsAfterNavigation = await requests();
    const returnedHomeRequests = requestsAfterNavigation.filter(
      (request) => request.pathname === "/home"
    ).length;
    assert.equal(returnedHomeRequests, initialHomeRequests);
  });
});
