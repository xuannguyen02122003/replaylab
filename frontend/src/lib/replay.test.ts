import { initialReplay, replayReducer, type ReplayAction, type ReplayState } from "./replay";

function run(actions: ReplayAction[], state: ReplayState = initialReplay(4)) {
  return actions.reduce(replayReducer, state);
}

describe("replayReducer", () => {
  it("starts outside replay mode", () => {
    expect(initialReplay(4)).toEqual({ index: null, playing: false, length: 4 });
  });

  it("play starts at the first event and ticks forward", () => {
    expect(run([{ type: "play" }])).toMatchObject({ index: 0, playing: true });
    expect(run([{ type: "play" }, { type: "tick" }, { type: "tick" }])).toMatchObject({ index: 2, playing: true });
  });

  it("stops playing at the last event", () => {
    const state = run([{ type: "play" }, { type: "tick" }, { type: "tick" }, { type: "tick" }, { type: "tick" }]);
    expect(state).toMatchObject({ index: 3, playing: false });
  });

  it("play at the end restarts from the beginning", () => {
    expect(run([{ type: "last" }, { type: "play" }])).toMatchObject({ index: 0, playing: true });
  });

  it("steps forward and backward without going out of range", () => {
    expect(run([{ type: "next" }, { type: "prev" }, { type: "prev" }]).index).toBe(0);
    expect(run([{ type: "last" }, { type: "next" }]).index).toBe(3);
  });

  it("manual steps pause playback", () => {
    expect(run([{ type: "play" }, { type: "next" }])).toMatchObject({ index: 1, playing: false });
  });

  it("ticks do nothing while paused", () => {
    expect(run([{ type: "play" }, { type: "pause" }, { type: "tick" }]).index).toBe(0);
  });

  it("seek clamps and stop leaves replay mode", () => {
    expect(run([{ type: "seek", index: 99 }]).index).toBe(3);
    expect(run([{ type: "seek", index: 2 }, { type: "stop" }]).index).toBeNull();
  });

  it("does nothing for an empty run", () => {
    expect(run([{ type: "play" }, { type: "next" }], initialReplay(0))).toEqual(initialReplay(0));
  });
});
