const store = {
  route: "advice",
  theme: localStorage.getItem("aq-theme") || "light",
  bookId: null,
  context: null,
  freshness: null,
};

export default store;
