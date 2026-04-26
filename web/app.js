const levels = [
  {
    id: "two-rooks-mate",
    title: "Level 1: Two Rooks Mate",
    tag: "Beginner endgame",
    description: "Use two separated rooks to restrict the lone black king.",
    goal: "Practice selecting a rook, choosing a row or column direction, then choosing the final square.",
    fen: "4k3/8/8/8/4K3/R7/8/1R6 w - - 0 1",
  },
  {
    id: "rook-box",
    title: "Level 2: Rook Box",
    tag: "Rook control",
    description: "One rook and king coordinate to reduce the black king's space.",
    goal: "Focus on rook movement and direction selection before exact-square selection.",
    fen: "6k1/8/8/8/4K3/8/8/5R2 w - - 0 1",
  },
  {
    id: "minor-piece-net",
    title: "Level 3: Minor Piece Net",
    tag: "Piece coordination",
    description: "White king, bishop, and knight coordinate against a lone king.",
    goal: "Preview future levels where bishops and knights are also selectable pieces.",
    fen: "7k/8/8/8/4K3/8/3B4/6N1 w - - 0 1",
  },
  {
    id: "mixed-endgame",
    title: "Level 4: Mixed Endgame",
    tag: "Full visual test",
    description: "A richer board case for checking piece images and layout.",
    goal: "Use this level to visually verify kings, rooks, bishops, knights, and pawns.",
    fen: "4k3/2n5/8/8/4K3/2B5/R6P/1R6 w - - 0 1",
  },
];

const calibrationSquares = [
  { label: "upper_left", square: 9 },   // B7
  { label: "upper_right", square: 14 }, // G7
  { label: "lower_left", square: 49 },  // B2
  { label: "lower_right", square: 54 }, // G2
];

const calibrationTargetPlan = [
  { label: "upper_right", cycles: 3 },
  { label: "upper_left", cycles: 2 },
  { label: "lower_left", cycles: 3 },
  { label: "lower_right", cycles: 2 },
];

const pieceImages = {
  K: "../assets/Figures/KingWhite.png",
  k: "../assets/Figures/KingBlack.png",
  R: "../assets/Figures/RookWhite.png",
  r: "../assets/Figures/RookBlack.png",
  N: "../assets/Figures/KnightWhite.png",
  n: "../assets/Figures/KnightBlack.png",
  B: "../assets/Figures/BishopWhite.png",
  b: "../assets/Figures/BishopBlack.png",
  P: "../assets/Figures/PawnWhite.png",
};

const fallbackPieces = {
  p: "P",
  q: "Q",
  Q: "Q",
};

const levelScreen = document.querySelector("#level-screen");
const boardScreen = document.querySelector("#board-screen");
const calibrationScreen = document.querySelector("#calibration-screen");
const levelsContainer = document.querySelector("#levels");
const mainBoard = document.querySelector("#main-board");
const calibrationBoard = document.querySelector("#calibration-board");
const calibrationBoardMessage = document.querySelector("#calibration-board-message");
const backButton = document.querySelector("#back-button");
const startOverButton = document.querySelector("#start-over-button");
const levelTitle = document.querySelector("#level-title");
const levelDescription = document.querySelector("#level-description");
const levelGoal = document.querySelector("#level-goal");
const levelFen = document.querySelector("#level-fen");
const flowStatus = document.querySelector("#flow-status");
const calibrationInstruction = document.querySelector("#calibration-instruction");
const calibrationStatus = document.querySelector("#calibration-status");
const winCelebration = document.querySelector("#win-celebration");
const celebrationKicker = document.querySelector("#celebration-kicker");
const celebrationTitle = document.querySelector("#celebration-title");
const celebrationMessage = document.querySelector("#celebration-message");

const flashDurationMs = 600;
const interFlashMs = 500;
const cyclesPerDecision = 5;
const startDelayMs = 5000;
const afterPieceDelayMs = 3000;
const opponentMoveDelayMs = 1200;
const opponentHighlightMs = 900;
const calibrationCycles = 10;
const calibrationInstructionSeconds = 4;

let currentBoard = [];
let currentLevel = null;
let selectedSquare = null;
let activeRunId = 0;
let pendingSelection = null;
let levelSelectionRunId = 0;
let navigationSelectionRunId = 0;

function parseFenBoard(fen) {
  const boardPart = fen.split(" ")[0];
  const squares = [];

  for (const rank of boardPart.split("/")) {
    for (const char of rank) {
      if (Number.isInteger(Number.parseInt(char, 10))) {
        const emptyCount = Number.parseInt(char, 10);
        for (let i = 0; i < emptyCount; i += 1) {
          squares.push(null);
        }
      } else {
        squares.push(char);
      }
    }
  }

  return squares;
}

function renderBoard(container, fen, { mini = false } = {}) {
  renderBoardFromSquares(container, parseFenBoard(fen), { mini });
}

function renderBoardFromSquares(container, squares, { mini = false, highlights = [], selected = null } = {}) {
  container.innerHTML = "";
  container.classList.toggle("mini-board", mini);
  const highlightedSquares = new Set(highlights);
  if (container === mainBoard && highlights.length > 0) {
    levelFen.textContent = formatHighlightedSquares(highlights);
  }

  squares.forEach((piece, index) => {
    const rankFromTop = Math.floor(index / 8);
    const file = index % 8;
    const square = document.createElement("div");
    square.className = `square ${(rankFromTop + file) % 2 === 0 ? "light" : "dark"}`;
    if (highlightedSquares.has(index)) {
      square.classList.add("highlight");
    }
    if (selected === index) {
      square.classList.add("selected");
    }

    if (piece) {
      const imagePath = pieceImages[piece];
      if (imagePath) {
        const image = document.createElement("img");
        image.className = "piece";
        image.src = imagePath;
        image.alt = piece;
        square.appendChild(image);
      } else {
        const fallback = document.createElement("span");
        fallback.className = "fallback-piece";
        fallback.textContent = fallbackPieces[piece] ?? piece.toUpperCase();
        square.appendChild(fallback);
      }
    }

    container.appendChild(square);
  });
}

function openLevel(level) {
  levelSelectionRunId += 1;
  clearLevelFlash();
  activeRunId += 1;
  navigationSelectionRunId += 1;
  clearNavigationFlash();
  currentLevel = level;
  currentBoard = parseFenBoard(level.fen);
  selectedSquare = null;
  levelTitle.textContent = level.title;
  levelDescription.textContent = level.description;
  levelGoal.textContent = level.goal;
  levelFen.textContent = "Waiting...";
  hideWinCelebration();
  flowStatus.textContent = "Board opened. Flashing starts in 5 seconds.";
  renderBoardFromSquares(mainBoard, currentBoard);
  levelScreen.classList.add("hidden");
  boardScreen.classList.remove("hidden");
  runBoardFlow(activeRunId);
}

function renderLevels() {
  levelsContainer.innerHTML = "";

  for (const level of levels) {
    const card = document.createElement("button");
    card.className = "level-card";
    card.type = "button";
    card.addEventListener("click", () => openLevel(level));

    const preview = document.createElement("div");
    preview.className = "chess-board mini-board";
    renderBoard(preview, level.fen, { mini: true });

    const text = document.createElement("div");
    text.innerHTML = `
      <div class="level-meta">${level.tag}</div>
      <h2>${level.title}</h2>
      <p>${level.description}</p>
    `;

    card.append(preview, text);
    levelsContainer.appendChild(card);
  }
}

backButton.addEventListener("click", goBackToLevels);
startOverButton.addEventListener("click", startOverLevel);

function goBackToLevels() {
  activeRunId += 1;
  navigationSelectionRunId += 1;
  pendingSelection = null;
  blurBoardActionButtons();
  clearNavigationFlash();
  hideWinCelebration();
  boardScreen.classList.add("hidden");
  levelScreen.classList.remove("hidden");
  startLevelSelectionFlow();
}

function startOverLevel() {
  if (!currentLevel) return;
  navigationSelectionRunId += 1;
  pendingSelection = null;
  blurBoardActionButtons();
  clearNavigationFlash();
  openLevel(currentLevel);
}

renderLevels();
startCalibrationFlow();

document.addEventListener("keydown", (event) => {
  if (event.code !== "Space") {
    return;
  }
  event.preventDefault();
  if (!pendingSelection) {
    return;
  }
  pendingSelection();
  pendingSelection = null;
});

async function runBoardFlow(runId) {
  await sleep(startDelayMs);
  if (!isActive(runId)) return;

  while (isActive(runId)) {
    const movablePieces = getSelectableWhitePieces(currentBoard);
    if (movablePieces.length === 0) {
      flowStatus.textContent = "No movable white pieces in this level.";
      return;
    }

    flowStatus.textContent = "Focus on a white piece. Press Space when it flashes.";
    const pieceChoice = await flashOptions(
      movablePieces.map((square) => [square]),
      runId,
    );
    if (pieceChoice === null) return;

    selectedSquare = movablePieces[pieceChoice];
    renderBoardFromSquares(mainBoard, currentBoard, { selected: selectedSquare });
    flowStatus.textContent = "Piece selected. Direction or square choices start in 3 seconds.";
    await sleep(afterPieceDelayMs);
    if (!isActive(runId)) return;

    const piece = currentBoard[selectedSquare];
    const moves = getSelectableMoves(currentBoard, selectedSquare);
    if (moves.length === 0) {
      flowStatus.textContent = "Selected piece has no moves. Restarting piece selection.";
      selectedSquare = null;
      continue;
    }

    let targetSquare;
    if (piece.toUpperCase() === "R") {
      targetSquare = await chooseRookTarget(selectedSquare, moves, runId);
    } else {
      flowStatus.textContent = "Focus on a destination box. Press Space when it flashes.";
      const targetChoice = await flashOptions(moves.map((square) => [square]), runId);
      if (targetChoice === null) return;
      targetSquare = moves[targetChoice];
    }

    movePiece(selectedSquare, targetSquare);
    selectedSquare = null;
    renderBoardFromSquares(mainBoard, currentBoard);
    const blackStatus = getGameStatus(currentBoard, false);
    if (blackStatus === "insufficient-material") {
      showDrawMessage("Insufficient Material", "Only kings are left. Choose what to do next.");
      return;
    }
    if (blackStatus === "checkmate") {
      showWinCelebration();
      return;
    }
    if (blackStatus === "stalemate") {
      showDrawMessage();
      return;
    }
    flowStatus.textContent = "White move applied. Opponent is thinking...";
    const shouldContinue = await playOpponentTurn(runId);
    if (!shouldContinue) return;
    await sleep(800);
  }
}

async function playOpponentTurn(runId) {
  await sleep(opponentMoveDelayMs);
  if (!isActive(runId)) return;

  const blackMoves = getAllLegalMoves(currentBoard, false);
  if (blackMoves.length === 0) {
    if (isInCheck(currentBoard, false)) {
      showWinCelebration();
    } else {
      showDrawMessage();
    }
    return false;
  }

  const chosenMove = chooseOpponentMove(blackMoves);
  flowStatus.textContent = "Opponent move.";
  renderBoardFromSquares(mainBoard, currentBoard, {
    highlights: [chosenMove.from, chosenMove.to],
  });
  await sleep(opponentHighlightMs);
  if (!isActive(runId)) return;

  movePiece(chosenMove.from, chosenMove.to);
  renderBoardFromSquares(mainBoard, currentBoard);
  if (getGameStatus(currentBoard, true) === "insufficient-material") {
    showDrawMessage("Insufficient Material", "Only kings are left. Choose what to do next.");
    return false;
  }
  flowStatus.textContent = "Opponent moved. Focus on a white piece.";
  return true;
}

async function chooseRookTarget(fromSquare, moves, runId) {
  const directionGroups = getRookDirectionGroups(fromSquare, moves);

  flowStatus.textContent = "Focus on a rook direction. Press Space when that path flashes.";
  const directionChoice = await flashOptions(directionGroups, runId);
  if (directionChoice === null) return null;

  const directionSquares = directionGroups[directionChoice];
  if (directionSquares.length === 1) {
    return directionSquares[0];
  }

  flowStatus.textContent = "Focus on the exact box inside that direction. Press Space when it flashes.";
  const targetChoice = await flashOptions(
    directionSquares.map((square) => [square]),
    runId,
  );
  if (targetChoice === null) return null;
  return directionSquares[targetChoice];
}

async function flashOptions(groups, runId) {
  for (let cycle = 0; cycle < cyclesPerDecision; cycle += 1) {
    for (let index = 0; index < groups.length; index += 1) {
      if (!isActive(runId)) return null;

      renderBoardFromSquares(mainBoard, currentBoard, {
        highlights: groups[index],
        selected: selectedSquare,
      });
      const selected = await waitForSelectionOrTimeout(flashDurationMs, index, runId);
      if (selected !== null) {
        return selected;
      }

      renderBoardFromSquares(mainBoard, currentBoard, { selected: selectedSquare });
      await sleep(interFlashMs);
    }
  }

  flowStatus.textContent = "No Space selection was made. Repeating this step.";
  levelFen.textContent = "Waiting...";
  return flashOptions(groups, runId);
}

function waitForSelectionOrTimeout(duration, index, runId) {
  return new Promise((resolve) => {
    let resolved = false;
    const timeoutId = window.setTimeout(() => {
      if (resolved) return;
      resolved = true;
      if (pendingSelection === chooseCurrent) {
        pendingSelection = null;
      }
      resolve(null);
    }, duration);

    function chooseCurrent() {
      if (resolved || !isActive(runId)) return;
      resolved = true;
      window.clearTimeout(timeoutId);
      resolve(index);
    }

    pendingSelection = chooseCurrent;
  });
}

function getSelectableWhitePieces(board) {
  const pieces = [];
  board.forEach((piece, index) => {
    if (piece && isWhite(piece) && getSelectableMoves(board, index).length > 0) {
      pieces.push(index);
    }
  });
  return pieces;
}

function getSelectableMoves(board, from) {
  return getPseudoLegalMoves(board, from);
}

function getAllLegalMoves(board, forWhite) {
  const moves = [];
  board.forEach((piece, index) => {
    if (!piece || isWhite(piece) !== forWhite) {
      return;
    }

    for (const target of getLegalMoves(board, index)) {
      moves.push({
        from: index,
        to: target,
        captures: Boolean(board[target]),
      });
    }
  });
  return moves;
}

function showWinCelebration() {
  activeRunId += 1;
  pendingSelection = null;
  flowStatus.textContent = "You won the game!";
  levelFen.textContent = "Victory";
  celebrationKicker.textContent = "Checkmate";
  celebrationTitle.textContent = "You Won!";
  celebrationMessage.textContent = "Beautiful finish. Return to levels when you are ready.";
  winCelebration.classList.remove("hidden");
  startNavigationChoiceFlow();
}

function showDrawMessage(reason = "Stalemate", message = "No legal move remains. Choose what to do next.") {
  activeRunId += 1;
  pendingSelection = null;
  flowStatus.textContent = `Draw by ${reason.toLowerCase()}.`;
  levelFen.textContent = "Draw";
  celebrationKicker.textContent = "";
  celebrationTitle.textContent = "This Is a Draw";
  celebrationMessage.textContent = message;
  winCelebration.classList.remove("hidden");
  startNavigationChoiceFlow();
}

function hideWinCelebration() {
  winCelebration.classList.add("hidden");
}

async function startNavigationChoiceFlow() {
  const runId = ++navigationSelectionRunId;
  const options = [
    { button: backButton, action: goBackToLevels, label: "Back to Levels" },
    { button: startOverButton, action: startOverLevel, label: "Start Over" },
  ];

  while (runId === navigationSelectionRunId && !winCelebration.classList.contains("hidden")) {
    for (let index = 0; index < options.length; index += 1) {
      if (runId !== navigationSelectionRunId || winCelebration.classList.contains("hidden")) return;

      const option = options[index];
      clearNavigationFlash();
      option.button.classList.add("button-flash");
      flowStatus.textContent = `Focus on ${option.label}. Press Space when it flashes.`;

      const selected = await waitForNavigationSelectionOrTimeout(flashDurationMs, index, runId);
      if (selected !== null) {
        clearNavigationFlash();
        option.action();
        return;
      }

      option.button.classList.remove("button-flash");
      await sleep(interFlashMs);
    }
  }

  clearNavigationFlash();
}

function clearNavigationFlash() {
  backButton.classList.remove("button-flash");
  startOverButton.classList.remove("button-flash");
}

function blurBoardActionButtons() {
  if (document.activeElement === backButton || document.activeElement === startOverButton) {
    document.activeElement.blur();
  }
}

function waitForNavigationSelectionOrTimeout(duration, index, runId) {
  return new Promise((resolve) => {
    let resolved = false;
    const timeoutId = window.setTimeout(() => {
      if (resolved) return;
      resolved = true;
      if (pendingSelection === chooseCurrent) {
        pendingSelection = null;
      }
      resolve(null);
    }, duration);

    function chooseCurrent() {
      if (resolved || runId !== navigationSelectionRunId) return;
      resolved = true;
      window.clearTimeout(timeoutId);
      resolve(index);
    }

    pendingSelection = chooseCurrent;
  });
}

function waitForLevelSelectionOrTimeout(duration, index, runId) {
  return new Promise((resolve) => {
    let resolved = false;
    const timeoutId = window.setTimeout(() => {
      if (resolved) return;
      resolved = true;
      if (pendingSelection === chooseCurrent) {
        pendingSelection = null;
      }
      resolve(null);
    }, duration);

    function chooseCurrent() {
      if (resolved || runId !== levelSelectionRunId || levelScreen.classList.contains("hidden")) return;
      resolved = true;
      window.clearTimeout(timeoutId);
      resolve(index);
    }

    pendingSelection = chooseCurrent;
  });
}

function chooseOpponentMove(moves) {
  const captures = moves.filter((move) => move.captures);
  const candidates = captures.length > 0 ? captures : moves;
  return candidates[Math.floor(Math.random() * candidates.length)];
}

function getGameStatus(board, forWhite) {
  if (hasInsufficientMaterial(board)) return "insufficient-material";
  const hasMoves = getAllLegalMoves(board, forWhite).length > 0;
  if (hasMoves) return "active";
  return isInCheck(board, forWhite) ? "checkmate" : "stalemate";
}

function hasInsufficientMaterial(board) {
  const pieces = board.filter(Boolean);
  return pieces.length === 2 && pieces.every((piece) => piece.toUpperCase() === "K");
}

function getLegalMoves(board, from) {
  const piece = board[from];
  if (!piece) return [];

  const movingWhite = isWhite(piece);
  return getPseudoLegalMoves(board, from).filter((target) => {
    const nextBoard = makeMoveOnBoard(board, from, target);
    return !isInCheck(nextBoard, movingWhite);
  });
}

function getPseudoLegalMoves(board, from) {
  const piece = board[from];
  if (!piece) return [];

  const type = piece.toUpperCase();
  if (type === "R") return slidingMoves(board, from, [[0, 1], [1, 0], [0, -1], [-1, 0]]);
  if (type === "B") return slidingMoves(board, from, [[1, 1], [1, -1], [-1, -1], [-1, 1]]);
  if (type === "Q") return slidingMoves(board, from, [[0, 1], [1, 0], [0, -1], [-1, 0], [1, 1], [1, -1], [-1, -1], [-1, 1]]);
  if (type === "N") return jumpMoves(board, from, [[1, 2], [2, 1], [2, -1], [1, -2], [-1, -2], [-2, -1], [-2, 1], [-1, 2]]);
  if (type === "K") return jumpMoves(board, from, [[0, 1], [1, 1], [1, 0], [1, -1], [0, -1], [-1, -1], [-1, 0], [-1, 1]]);
  if (type === "P") return pawnMoves(board, from, piece);
  return [];
}

function slidingMoves(board, from, directions) {
  const moves = [];
  const { file, rank } = indexToCoord(from);
  const movingWhite = isWhite(board[from]);

  for (const [df, dr] of directions) {
    let nextFile = file + df;
    let nextRank = rank + dr;
    while (isOnBoard(nextFile, nextRank)) {
      const target = coordToIndex(nextFile, nextRank);
      const targetPiece = board[target];
      if (!targetPiece) {
        moves.push(target);
      } else {
        if (isWhite(targetPiece) !== movingWhite && targetPiece.toUpperCase() !== "K") {
          moves.push(target);
        }
        break;
      }
      nextFile += df;
      nextRank += dr;
    }
  }

  return moves;
}

function jumpMoves(board, from, jumps) {
  const moves = [];
  const { file, rank } = indexToCoord(from);
  const movingWhite = isWhite(board[from]);

  for (const [df, dr] of jumps) {
    const nextFile = file + df;
    const nextRank = rank + dr;
    if (!isOnBoard(nextFile, nextRank)) continue;
    const target = coordToIndex(nextFile, nextRank);
    const targetPiece = board[target];
    if (!targetPiece || (isWhite(targetPiece) !== movingWhite && targetPiece.toUpperCase() !== "K")) {
      moves.push(target);
    }
  }

  return moves;
}

function pawnMoves(board, from, piece) {
  const moves = [];
  const { file, rank } = indexToCoord(from);
  const direction = isWhite(piece) ? 1 : -1;
  const forwardRank = rank + direction;

  if (isOnBoard(file, forwardRank)) {
    const forward = coordToIndex(file, forwardRank);
    if (!board[forward]) {
      moves.push(forward);
    }
  }

  for (const df of [-1, 1]) {
    const targetFile = file + df;
    if (!isOnBoard(targetFile, forwardRank)) continue;
    const target = coordToIndex(targetFile, forwardRank);
    if (board[target] && isWhite(board[target]) !== isWhite(piece) && board[target].toUpperCase() !== "K") {
      moves.push(target);
    }
  }

  return moves;
}

function isInCheck(board, forWhite) {
  const kingSquare = findKing(board, forWhite);
  if (kingSquare === null) return true;
  return isSquareAttacked(board, kingSquare, !forWhite);
}

function findKing(board, forWhite) {
  const king = forWhite ? "K" : "k";
  const square = board.indexOf(king);
  return square === -1 ? null : square;
}

function isSquareAttacked(board, square, byWhite) {
  return board.some((piece, from) => {
    if (!piece || isWhite(piece) !== byWhite) return false;
    return attacksSquare(board, from, square);
  });
}

function attacksSquare(board, from, target) {
  const piece = board[from];
  if (!piece) return false;

  const { file: fromFile, rank: fromRank } = indexToCoord(from);
  const { file: targetFile, rank: targetRank } = indexToCoord(target);
  const fileDelta = targetFile - fromFile;
  const rankDelta = targetRank - fromRank;
  const type = piece.toUpperCase();

  if (type === "P") {
    const direction = isWhite(piece) ? 1 : -1;
    return rankDelta === direction && Math.abs(fileDelta) === 1;
  }

  if (type === "N") {
    return (
      (Math.abs(fileDelta) === 1 && Math.abs(rankDelta) === 2)
      || (Math.abs(fileDelta) === 2 && Math.abs(rankDelta) === 1)
    );
  }

  if (type === "K") {
    return Math.max(Math.abs(fileDelta), Math.abs(rankDelta)) === 1;
  }

  if (type === "R") {
    return (fileDelta === 0 || rankDelta === 0) && isPathClear(board, from, target);
  }

  if (type === "B") {
    return Math.abs(fileDelta) === Math.abs(rankDelta) && isPathClear(board, from, target);
  }

  if (type === "Q") {
    const straight = fileDelta === 0 || rankDelta === 0;
    const diagonal = Math.abs(fileDelta) === Math.abs(rankDelta);
    return (straight || diagonal) && isPathClear(board, from, target);
  }

  return false;
}

function isPathClear(board, from, target) {
  const { file: fromFile, rank: fromRank } = indexToCoord(from);
  const { file: targetFile, rank: targetRank } = indexToCoord(target);
  const fileStep = Math.sign(targetFile - fromFile);
  const rankStep = Math.sign(targetRank - fromRank);
  let nextFile = fromFile + fileStep;
  let nextRank = fromRank + rankStep;

  while (nextFile !== targetFile || nextRank !== targetRank) {
    if (board[coordToIndex(nextFile, nextRank)]) return false;
    nextFile += fileStep;
    nextRank += rankStep;
  }

  return true;
}

function getRookDirectionGroups(fromSquare, moves) {
  const { file: fromFile, rank: fromRank } = indexToCoord(fromSquare);
  const groups = {
    up: [],
    right: [],
    down: [],
    left: [],
  };

  for (const square of moves) {
    const { file, rank } = indexToCoord(square);
    if (file === fromFile && rank > fromRank) groups.up.push(square);
    if (file > fromFile && rank === fromRank) groups.right.push(square);
    if (file === fromFile && rank < fromRank) groups.down.push(square);
    if (file < fromFile && rank === fromRank) groups.left.push(square);
  }

  return ["up", "right", "down", "left"]
    .map((direction) => groups[direction].sort((a, b) => distance(fromSquare, a) - distance(fromSquare, b)))
    .filter((group) => group.length > 0);
}

function movePiece(from, to) {
  currentBoard[to] = currentBoard[from];
  currentBoard[from] = null;
}

function makeMoveOnBoard(board, from, to) {
  const nextBoard = board.slice();
  nextBoard[to] = nextBoard[from];
  nextBoard[from] = null;
  return nextBoard;
}

function indexToCoord(index) {
  return {
    file: index % 8,
    rank: 7 - Math.floor(index / 8),
  };
}

function formatSquare(index) {
  const { file, rank } = indexToCoord(index);
  return `${"abcdefgh"[file]}${rank + 1}`;
}

function formatHighlightedSquares(squares) {
  return squares.map((square) => formatSquare(square)).join(", ");
}

function coordToIndex(file, rank) {
  return (7 - rank) * 8 + file;
}

function isOnBoard(file, rank) {
  return file >= 0 && file < 8 && rank >= 0 && rank < 8;
}

function isWhite(piece) {
  return piece === piece.toUpperCase();
}

function distance(from, to) {
  const a = indexToCoord(from);
  const b = indexToCoord(to);
  return Math.abs(a.file - b.file) + Math.abs(a.rank - b.rank);
}

function sleep(duration) {
  return new Promise((resolve) => window.setTimeout(resolve, duration));
}

function isActive(runId) {
  return runId === activeRunId && currentLevel !== null;
}

async function startLevelSelectionFlow() {
  levelSelectionRunId += 1;
  const runId = levelSelectionRunId;
  pendingSelection = null;
  clearLevelFlash();

  await sleep(800);

  while (runId === levelSelectionRunId && !levelScreen.classList.contains("hidden")) {
    for (let index = 0; index < levels.length; index += 1) {
      if (runId !== levelSelectionRunId || levelScreen.classList.contains("hidden")) {
        clearLevelFlash();
        return;
      }

      setFlashingLevel(index);
      const selected = await waitForLevelSelectionOrTimeout(flashDurationMs, index, runId);
      if (selected !== null) {
        clearLevelFlash();
        openLevel(levels[selected]);
        return;
      }

      clearLevelFlash();
      await sleep(interFlashMs);
    }
  }
}

function setFlashingLevel(index) {
  const cards = levelsContainer.querySelectorAll(".level-card");
  cards.forEach((card, cardIndex) => {
    card.classList.toggle("level-flash", cardIndex === index);
  });
}

function clearLevelFlash() {
  levelsContainer.querySelectorAll(".level-card").forEach((card) => {
    card.classList.remove("level-flash");
  });
}

async function startCalibrationFlow() {
  calibrationScreen.classList.remove("hidden");
  levelScreen.classList.add("hidden");
  boardScreen.classList.add("hidden");

  const emptyBoard = Array(64).fill(null);
  renderBoardFromSquares(calibrationBoard, emptyBoard);

  calibrationInstruction.textContent = "Click space to start calibration";
  calibrationStatus.textContent = "Initializing calibration...";

  // Wait for space press
  await new Promise((resolve) => {
    const handler = (event) => {
      if (event.code === "Space") {
        event.preventDefault();
        document.removeEventListener("keydown", handler);
        resolve();
      }
    };
    document.addEventListener("keydown", handler);
  });

  // Shuffle the target plan
  const shuffledPlan = [...calibrationTargetPlan].sort(() => Math.random() - 0.5);

  let cycleOffset = 0;
  for (const target of shuffledPlan) {
    const targetSquare = calibrationSquares.find(s => s.label === target.label).square;
    const message = `Calibration:\nFocus ${target.label.replace("_", " ").toUpperCase()}`;
    calibrationBoardMessage.textContent = message;
    calibrationBoardMessage.classList.remove("hidden");
    calibrationStatus.textContent = `Focusing on ${target.label.replace("_", " ")}`;
    renderBoardFromSquares(calibrationBoard, emptyBoard, { highlights: [targetSquare] });
    await sleep(2000);
    calibrationBoardMessage.classList.add("hidden");

    // Flash the groups
    for (let cycle = 0; cycle < target.cycles; cycle++) {
      for (const square of calibrationSquares) {
        const isTarget = square.label === target.label;
        renderBoardFromSquares(calibrationBoard, emptyBoard, { highlights: [square.square] });
        await sleep(flashDurationMs);
        renderBoardFromSquares(calibrationBoard, emptyBoard);
        await sleep(interFlashMs);
      }
    }
    cycleOffset += target.cycles;
  }

  calibrationInstruction.textContent = "Calibration complete.";
  calibrationStatus.textContent = "System ready. Proceeding to level selection...";
  await sleep(2000);

  calibrationScreen.classList.add("hidden");
  levelScreen.classList.remove("hidden");
  startLevelSelectionFlow();
}
