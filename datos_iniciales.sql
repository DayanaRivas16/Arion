--
-- PostgreSQL database dump
--

\restrict gvmRizoHXFElfQhs6Ui2kS0tib0ZBDnsEhHLsaAVJ1jVGmP5NWUXLetgi4Zwp1n

-- Dumped from database version 18.4
-- Dumped by pg_dump version 18.4

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: categorias; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.categorias (id_categoria, nombre_categoria, descripcion) FROM stdin;
1	Tecnología	Proyectos de software, hardware y automatización
2	Diseño	Proyectos visuales, gráficos y UX/UI
3	IA	Inteligencia artificial y modelos de aprendizaje
4	Sostenibilidad	Proyectos ecológicos y energías limpias
5	Educación	Herramientas y métodos para el aprendizaje
6	Salud	Innovaciones biomédicas y de bienestar
7	Arte	Expresiones artísticas y multidisciplinarias
8	Ciencia	Investigación científica y experimentación
\.


--
-- Data for Name: dominios_permitidos; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.dominios_permitidos (id_dominio, dominio) FROM stdin;
2	sagradafamiliapalmira.edu.co
\.


--
-- Data for Name: tipos_usuario; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.tipos_usuario (id_tipo, nombre_tipo) FROM stdin;
1	Estudiante
2	Docente
3	Administrador
\.


--
-- Name: categorias_id_categoria_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.categorias_id_categoria_seq', 8, true);


--
-- Name: dominios_permitidos_id_dominio_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.dominios_permitidos_id_dominio_seq', 1, true);


--
-- Name: tipos_usuario_id_tipo_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.tipos_usuario_id_tipo_seq', 3, true);


--
-- PostgreSQL database dump complete
--

\unrestrict gvmRizoHXFElfQhs6Ui2kS0tib0ZBDnsEhHLsaAVJ1jVGmP5NWUXLetgi4Zwp1n

