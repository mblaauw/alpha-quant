const store = {
  route: "desk",
  theme: localStorage.getItem("aq-theme") || "light",
  bookId: null,
  books: [],
  context: null,
  drawer: null,
  filters: {},
  freshness: null,   // cached /v1/console/freshness response
};

export default store;
