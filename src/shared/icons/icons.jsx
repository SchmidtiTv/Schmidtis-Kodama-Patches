/**
 * The app's named icons, drawn from Tabler (`@tabler/icons-react`) through the shared `Icon`
 * component. Each export keeps the props older call sites use:
 *
 *   size    number or CSS length; defaults to 1em so the icon follows the text size
 *   weight  "fill" | "duotone" → the filled Tabler variant when there is one, else a heavier stroke
 *           "bold"             → a heavier stroke
 *           anything else      → the regular 1.75 stroke
 *
 * New code may also render `<Icon icon={IconSomething} />` from "@/shared/ui/icon.jsx" directly.
 */

import React from "react";
import {
  IconAccessible,
  IconAdjustmentsHorizontal,
  IconAlertCircle,
  IconArrowLeft,
  IconArrowRight,
  IconArrowsDiagonal,
  IconArrowsDiagonalMinimize2,
  IconArrowsLeftRight,
  IconArrowsMaximize,
  IconArrowsMinimize,
  IconArrowsShuffle,
  IconArrowsSort,
  IconBell,
  IconBellFilled,
  IconBooks,
  IconBrandApplePodcast,
  IconBrandBluesky,
  IconBrandDiscord,
  IconBrandDiscordFilled,
  IconBrandGithub,
  IconBrandGithubFilled,
  IconBrandLastfm,
  IconBrandTiktok,
  IconBrandTiktokFilled,
  IconBrandTwitch,
  IconBrandYoutube,
  IconBrandYoutubeFilled,
  IconBrush,
  IconBug,
  IconBugFilled,
  IconBuildingStore,
  IconCaretDown,
  IconCaretDownFilled,
  IconCaretLeft,
  IconCaretLeftFilled,
  IconCaretRight,
  IconCaretRightFilled,
  IconCaretUp,
  IconCaretUpFilled,
  IconChartBar,
  IconCheck,
  IconChevronsLeft,
  IconChevronsRight,
  IconChevronsUp,
  IconCircle,
  IconCircleArrowUp,
  IconCircleArrowUpFilled,
  IconCircleCheck,
  IconCircleCheckFilled,
  IconCircleFilled,
  IconCircleHalf2,
  IconClipboard,
  IconClock,
  IconClockFilled,
  IconColorPicker,
  IconColorSwatch,
  IconCopy,
  IconCrown,
  IconCrownFilled,
  IconCut,
  IconDeviceFloppy,
  IconDeviceGamepad2,
  IconDeviceMobile,
  IconDeviceTv,
  IconDisc,
  IconDotsVertical,
  IconDownload,
  IconDroplet,
  IconDropletFilled,
  IconEar,
  IconExternalLink,
  IconEye,
  IconEyeFilled,
  IconEyeOff,
  IconFileExport,
  IconFileImport,
  IconFlag,
  IconFlagFilled,
  IconFlask,
  IconFolder,
  IconFolderFilled,
  IconFolderOpen,
  IconGlobe,
  IconGripHorizontal,
  IconGripVertical,
  IconHaze,
  IconHeadphones,
  IconHeadphonesFilled,
  IconHeart,
  IconHeartFilled,
  IconHistory,
  IconHome,
  IconHomeFilled,
  IconInfoCircle,
  IconInfoCircleFilled,
  IconKey,
  IconKeyboard,
  IconLayersDifference,
  IconLayersLinked,
  IconLayoutColumns,
  IconLayoutGrid,
  IconLayoutGridFilled,
  IconLink,
  IconList,
  IconListNumbers,
  IconLock,
  IconLockOpen,
  IconLogout,
  IconMessage,
  IconMessageFilled,
  IconMicrophone,
  IconMicrophone2,
  IconMicrophoneFilled,
  IconMinus,
  IconMoon,
  IconMoonFilled,
  IconMoonStars,
  IconMovie,
  IconMug,
  IconMugFilled,
  IconMusic,
  IconPaint,
  IconPaintFilled,
  IconPalette,
  IconPaletteFilled,
  IconPencil,
  IconPhoto,
  IconPin,
  IconPinFilled,
  IconPlayerPause,
  IconPlayerPauseFilled,
  IconPlayerPlay,
  IconPlayerPlayFilled,
  IconPlayerSkipBack,
  IconPlayerSkipBackFilled,
  IconPlayerSkipForward,
  IconPlayerSkipForwardFilled,
  IconPlaylist,
  IconPlus,
  IconPointer,
  IconPointerFilled,
  IconPower,
  IconPuzzle,
  IconPuzzleFilled,
  IconRadio,
  IconRefresh,
  IconRepeat,
  IconRepeatOnce,
  IconRobot,
  IconRotateClockwise,
  IconSearch,
  IconSend,
  IconSettings,
  IconSettingsFilled,
  IconShape,
  IconShare,
  IconSortAscending,
  IconSortDescending,
  IconSpeakerphone,
  IconStar,
  IconStarFilled,
  IconSun,
  IconSunFilled,
  IconTag,
  IconTagFilled,
  IconTextSize,
  IconTrash,
  IconTrashFilled,
  IconUpload,
  IconUserCheck,
  IconUserCircle,
  IconUserPlus,
  IconUsers,
  IconVinyl,
  IconVolume,
  IconVolume2,
  IconVolume3,
  IconWand,
  IconWaveSine,
  IconWifi,
  IconWifiOff,
  IconWind,
  IconX,
} from "@tabler/icons-react";
import Icon from "@/shared/ui/icon.jsx";

// Kept so existing <IconContext.Provider> wrappers keep rendering. Icons do not read it.
export const IconContext = React.createContext({});

const BOLD_STROKE = 2.25;

/**
 * Builds a named icon from a Tabler outline icon and, when Tabler has one, its filled variant.
 * `alwaysFilled` marks icons that are always drawn solid, whatever `weight` says.
 */
function tabler(outline, filled = null, { alwaysFilled = false } = {}) {
  return function TablerNamedIcon({ size = "1em", weight, stroke, ...rest }) {
    const wantsFill = alwaysFilled || weight === "fill" || weight === "duotone";
    if (wantsFill && filled) return <Icon icon={filled} size={size} {...rest} />;
    const heavy = wantsFill || weight === "bold";
    return (
      <Icon
        icon={outline}
        size={size}
        stroke={stroke ?? (heavy ? BOLD_STROKE : undefined)}
        {...rest}
      />
    );
  };
}

// Brand logos are solid marks, so they use the filled variant whenever Tabler has one.
function brand(outline, filled = null) {
  return tabler(outline, filled, { alwaysFilled: true });
}

// For the rare icon Tabler has no good match for. Rendered as a CSS mask so it still takes its
// color from currentColor like every Tabler icon, instead of a flat <img>.
function svgIcon(path) {
  return function MaskIcon({ size = 16, className = "", style, ...rest }) {
    return (
      <span
        aria-hidden="true"
        className={className}
        style={{
          display: "inline-block",
          width: size,
          height: size,
          backgroundColor: "currentColor",
          WebkitMaskImage: `url(${path})`,
          maskImage: `url(${path})`,
          WebkitMaskSize: "contain",
          maskSize: "contain",
          WebkitMaskRepeat: "no-repeat",
          maskRepeat: "no-repeat",
          WebkitMaskPosition: "center",
          maskPosition: "center",
          ...style,
        }}
        {...rest}
      />
    );
  };
}

// ── Window controls ──────────────────────────────────────────────────────────
export const Minus = tabler(IconMinus);
export const X = tabler(IconX);

// ── Playback ─────────────────────────────────────────────────────────────────
export const Play = tabler(IconPlayerPlay, IconPlayerPlayFilled);
export const Pause = tabler(IconPlayerPause, IconPlayerPauseFilled);
export const SkipBack = tabler(IconPlayerSkipBack, IconPlayerSkipBackFilled);
export const SkipForward = tabler(IconPlayerSkipForward, IconPlayerSkipForwardFilled);
export const Shuffle = tabler(IconArrowsShuffle);
export const Repeat = tabler(IconRepeat);
export const RepeatOnce = tabler(IconRepeatOnce);
export const PlayCircle = tabler(IconPlayerPlay, IconPlayerPlayFilled);

// ── Volume ───────────────────────────────────────────────────────────────────
export const SpeakerX = tabler(IconVolume3);
export const SpeakerLow = tabler(IconVolume2);
export const SpeakerHigh = tabler(IconVolume);

// ── Navigation ───────────────────────────────────────────────────────────────
export const House = tabler(IconHome, IconHomeFilled);
export const Books = tabler(IconBooks);
export const MagnifyingGlass = tabler(IconSearch);
export const ArrowLeft = tabler(IconArrowLeft);
export const CaretLeft = tabler(IconCaretLeft, IconCaretLeftFilled);
export const CaretRight = tabler(IconCaretRight, IconCaretRightFilled);
export const CaretLineLeft = tabler(IconChevronsLeft);
export const CaretLineRight = tabler(IconChevronsRight);
export const CaretUp = tabler(IconCaretUp, IconCaretUpFilled);
export const CaretDown = tabler(IconCaretDown, IconCaretDownFilled);
export const CaretLineUp = tabler(IconChevronsUp);

// ── Player UI ────────────────────────────────────────────────────────────────
export const Queue = tabler(IconList);
export const ChatText = tabler(IconMessage, IconMessageFilled);
export const ArrowsIn = tabler(IconArrowsMinimize);
export const ArrowsOut = tabler(IconArrowsMaximize);
export const MiniPlayerEnter = tabler(IconArrowsDiagonalMinimize2, null, { alwaysFilled: true });
export const MiniPlayerExit = tabler(IconArrowsDiagonal, null, { alwaysFilled: true });

// ── Settings & tools ─────────────────────────────────────────────────────────
export const Gear = tabler(IconSettings, IconSettingsFilled);
export const Palette = tabler(IconPalette, IconPaletteFilled);
export const Key = tabler(IconKey);
export const Keyboard = tabler(IconKeyboard);
export const PaintBrushBroad = tabler(IconBrush);
export const HardDrives = tabler(IconDisc);
export const FolderOpen = tabler(IconFolderOpen);
export const Translate = tabler(IconGlobe);
// Lyrics-only actions. Deliberately separate from `Translate`, which stands for the interface
// language in the settings and the sidebar — same word, different meaning. Tabler has nothing
// that reads as romanisation, so both are drawn icons.
export const TranslateLyrics = svgIcon("/translate.svg");
export const Romanization = svgIcon("/romanization.svg");
export const Robot = tabler(IconRobot);
export const Eyedropper = tabler(IconColorPicker);

// ── Content ──────────────────────────────────────────────────────────────────
export const VinylRecord = tabler(IconVinyl);
export const MusicNote = tabler(IconMusic);
export const Playlist = tabler(IconPlaylist);
export const ImageSquare = tabler(IconPhoto);
export const Microphone = tabler(IconMicrophone, IconMicrophoneFilled);
export const Headphones = tabler(IconHeadphones, IconHeadphonesFilled);
export const HeadphonesSimple = tabler(IconHeadphones, IconHeadphonesFilled);
export const Columns = tabler(IconLayoutColumns);
export const MicrophoneStand = tabler(IconMicrophone2, null, { alwaysFilled: true });
export const ClapperboardPlay = tabler(IconMovie);
export const Gamepad = tabler(IconDeviceGamepad2);
export const PodcastIcon = tabler(IconBrandApplePodcast);
export const Heart = tabler(IconHeart, IconHeartFilled);
export const Crown = tabler(IconCrown, IconCrownFilled);
export const UserPlus = tabler(IconUserPlus);
export const UserCheck = tabler(IconUserCheck);
export const UserCircle = tabler(IconUserCircle);
export const Users = tabler(IconUsers);
export const SignOut = tabler(IconLogout);
export const Power = tabler(IconPower);

// ── Actions ──────────────────────────────────────────────────────────────────
export const Check = tabler(IconCheck);
export const CheckCircle = tabler(IconCircleCheck, IconCircleCheckFilled);
export const Plus = tabler(IconPlus);
export const DownloadSimple = tabler(IconDownload);
export const UploadSimple = tabler(IconUpload);
export const Trash = tabler(IconTrash, IconTrashFilled);
export const PencilSimple = tabler(IconPencil);
export const ArrowCircleUp = tabler(IconCircleArrowUp, IconCircleArrowUpFilled);
export const Copy = tabler(IconCopy);
export const ArrowSquareOut = tabler(IconExternalLink);
export const ArrowClockwise = tabler(IconRotateClockwise);
export const ArrowsClockwise = tabler(IconRefresh);
export const ArrowsLeftRight = tabler(IconArrowsLeftRight);
export const Link = tabler(IconLink);
export const PushPin = tabler(IconPin, IconPinFilled);
export const ClockCounterClockwise = tabler(IconHistory);
export const Clock = tabler(IconClock, IconClockFilled);
export const Sort = tabler(IconArrowsSort, null, { alwaysFilled: true });
export const SortUp = tabler(IconSortAscending, null, { alwaysFilled: true });
export const SortDown = tabler(IconSortDescending, null, { alwaysFilled: true });

// ── Lists & layout ───────────────────────────────────────────────────────────
export const DotsSixVertical = tabler(IconGripVertical);
export const CursorArrow = tabler(IconPointer, IconPointerFilled);
export const GripLines = tabler(IconGripHorizontal);
export const DotsThreeVertical = tabler(IconDotsVertical);

// ── Time & weather (greeting) ────────────────────────────────────────────────
export const SunHorizon = tabler(IconMug, IconMugFilled, { alwaysFilled: true });
export const Sun = tabler(IconSun, IconSunFilled, { alwaysFilled: true });
export const CloudSun = tabler(IconHaze, null, { alwaysFilled: true });
export const Moon = tabler(IconMoon, IconMoonFilled, { alwaysFilled: true });
export const MoonStars = tabler(IconMoonStars, null, { alwaysFilled: true });

// ── Status ───────────────────────────────────────────────────────────────────
export const WifiHigh = tabler(IconWifi);
export const WifiX = tabler(IconWifiOff);
export const DeviceMobile = tabler(IconDeviceMobile);
export const Bug = tabler(IconBug, IconBugFilled);
export const PersonArmsSpread = tabler(IconAccessible);
export const Bell = tabler(IconBell, IconBellFilled);
export const Megaphone = tabler(IconSpeakerphone);
export const PaperPlaneTilt = tabler(IconSend);

// ── Overlay / Design ─────────────────────────────────────────────────────────
export const FloppyDisk = tabler(IconDeviceFloppy);
export const Swatches = tabler(IconColorSwatch);

// ── Settings icons ────────────────────────────────────────────────────────────
export const TextSize = tabler(IconTextSize);
export const Sliders = tabler(IconAdjustmentsHorizontal);
export const Eye = tabler(IconEye, IconEyeFilled);
export const EyeSlash = tabler(IconEyeOff);
export const Tag = tabler(IconTag, IconTagFilled);
export const CircleHalf = tabler(IconCircleHalf2);
export const WaveformLines = tabler(IconWaveSine);
export const Radio = tabler(IconRadio);
export const Sparkles = tabler(IconWand);
export const Flask = tabler(IconFlask);
export const ShareNodes = tabler(IconShare);
export const Globe = tabler(IconGlobe);
export const Lock = tabler(IconLock);
export const LockOpen = tabler(IconLockOpen);
export const ScreencastSimple = tabler(IconDeviceTv);
export const CircleFill = tabler(IconCircle, IconCircleFilled, { alwaysFilled: true });
export const Info = tabler(IconInfoCircle, IconInfoCircleFilled);
export const WarningCircle = tabler(IconAlertCircle);
export const Flag = tabler(IconFlag, IconFlagFilled);
export const Star = tabler(IconStar, IconStarFilled, { alwaysFilled: true });

// ── Brand icons ───────────────────────────────────────────────────────────────
export const BrandTwitch = brand(IconBrandTwitch);
export const BrandYoutube = brand(IconBrandYoutube, IconBrandYoutubeFilled);
export const BrandBluesky = brand(IconBrandBluesky);
export const BrandTiktok = brand(IconBrandTiktok, IconBrandTiktokFilled);
export const BrandLastfm = brand(IconBrandLastfm);
export const BrandGithub = brand(IconBrandGithub, IconBrandGithubFilled);
export const BrandDiscord = brand(IconBrandDiscord, IconBrandDiscordFilled);
export const MugHot = tabler(IconMug, IconMugFilled);

export const ArrowRight = tabler(IconArrowRight);
export const ObjectGroup = tabler(IconLayersLinked);
export const ObjectUngroup = tabler(IconLayersDifference);
export const PaintRoller = tabler(IconPaint, IconPaintFilled);
export const Shapes = tabler(IconShape);
export const Folder = tabler(IconFolder, IconFolderFilled);
export const PuzzlePiece = tabler(IconPuzzle, IconPuzzleFilled);
export const Storefront = tabler(IconBuildingStore);
export const GridTwo = tabler(IconLayoutGrid, IconLayoutGridFilled);
export const Droplet = tabler(IconDroplet, IconDropletFilled);
export const FileImport = tabler(IconFileImport);
export const FileExport = tabler(IconFileExport);
export const Scissors = tabler(IconCut);
export const Clipboard = tabler(IconClipboard);
export const Wind = tabler(IconWind);
export const EarListen = tabler(IconEar);
export const Bullhorn = tabler(IconSpeakerphone);
export const ListNumbers = tabler(IconListNumbers);
export const ChartBar = tabler(IconChartBar);
export const EqualizerIcon = svgIcon("/equalizer/eq-icon.svg");
export const OvlOpacity = svgIcon("/overlay-editor/opacity-icon.svg");
export const OvlCornerRadius = svgIcon("/overlay-editor/corner-radius-icon.svg"); // all four corners
export const OvlCornerSingle = svgIcon("/overlay-editor/corner-radius-single-icon.svg"); // one corner, rotated for the rest
export const OvlStrokeWeight = svgIcon("/overlay-editor/stroke-weight-icon.svg");
export const OvlDropShadow = svgIcon("/overlay-editor/drop-shadow-icon.svg");
export const OvlInnerShadow = svgIcon("/overlay-editor/inner-shadow-icon.svg");
export const OvlGlow = svgIcon("/overlay-editor/glow-icon.svg");
export const OvlLayerBlur = svgIcon("/overlay-editor/layer-blur-icon.svg");
export const OvlBackgroundBlur = svgIcon("/overlay-editor/background-blur-icon.svg");
