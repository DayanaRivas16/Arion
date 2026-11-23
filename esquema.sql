--
-- PostgreSQL database dump
--

\restrict 0TDhDwqimImlRJtDMU7nTrCoPxi9w2BNUmDzC5190yyIvMTYxO4qSgebbLWwu8g

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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: categorias; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categorias (
    id_categoria integer NOT NULL,
    nombre_categoria character varying(100) NOT NULL,
    descripcion text
);


--
-- Name: categorias_id_categoria_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.categorias_id_categoria_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: categorias_id_categoria_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.categorias_id_categoria_seq OWNED BY public.categorias.id_categoria;


--
-- Name: configuracion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.configuracion (
    clave character varying(50) NOT NULL,
    valor text NOT NULL
);


--
-- Name: documentos_proyecto; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documentos_proyecto (
    id_documento integer NOT NULL,
    id_proyecto integer,
    nombre_archivo character varying(255) NOT NULL,
    url_archivo text NOT NULL,
    tipo_documento character varying(50),
    tamano_bytes integer,
    fecha_subida timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: documentos_proyecto_id_documento_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.documentos_proyecto_id_documento_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: documentos_proyecto_id_documento_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.documentos_proyecto_id_documento_seq OWNED BY public.documentos_proyecto.id_documento;


--
-- Name: dominios_permitidos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dominios_permitidos (
    id_dominio integer NOT NULL,
    dominio character varying(100) NOT NULL
);


--
-- Name: dominios_permitidos_id_dominio_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dominios_permitidos_id_dominio_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dominios_permitidos_id_dominio_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dominios_permitidos_id_dominio_seq OWNED BY public.dominios_permitidos.id_dominio;


--
-- Name: etiquetas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.etiquetas (
    id_etiqueta integer NOT NULL,
    nombre_etiqueta character varying(100) NOT NULL
);


--
-- Name: etiquetas_id_etiqueta_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.etiquetas_id_etiqueta_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: etiquetas_id_etiqueta_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.etiquetas_id_etiqueta_seq OWNED BY public.etiquetas.id_etiqueta;


--
-- Name: permisos_rol; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.permisos_rol (
    accion character varying(30) NOT NULL,
    rol character varying(15) NOT NULL,
    permitido boolean DEFAULT false NOT NULL
);


--
-- Name: proyecto_colaboradores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proyecto_colaboradores (
    id_proyecto integer NOT NULL,
    id_usuario integer NOT NULL,
    rol_en_equipo character varying(100) DEFAULT 'Integrante'::character varying
);


--
-- Name: proyecto_likes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proyecto_likes (
    id_proyecto integer NOT NULL,
    id_usuario integer NOT NULL,
    fecha_like timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: proyecto_valoraciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proyecto_valoraciones (
    id_proyecto integer NOT NULL,
    id_usuario integer NOT NULL,
    puntuacion smallint NOT NULL,
    fecha_valoracion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT proyecto_valoraciones_puntuacion_check CHECK (((puntuacion >= 1) AND (puntuacion <= 5)))
);


--
-- Name: proyectos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proyectos (
    id_proyecto integer NOT NULL,
    titulo character varying(200) NOT NULL,
    descripcion text NOT NULL,
    imagen_portada text,
    profesor_a_cargo character varying(150) NOT NULL,
    grado character varying(50) NOT NULL,
    estado character varying(30) DEFAULT 'Publicado'::character varying,
    es_destacado boolean DEFAULT false,
    vistas_count integer DEFAULT 0,
    likes_count integer DEFAULT 0,
    calificacion numeric(2,1) DEFAULT NULL::numeric,
    id_usuario integer,
    id_categoria integer,
    fecha_creacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    motivo_rechazo text
);


--
-- Name: proyectos_etiquetas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proyectos_etiquetas (
    id_proyecto integer NOT NULL,
    id_etiqueta integer NOT NULL
);


--
-- Name: proyectos_id_proyecto_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proyectos_id_proyecto_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proyectos_id_proyecto_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proyectos_id_proyecto_seq OWNED BY public.proyectos.id_proyecto;


--
-- Name: reportes_proyecto; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reportes_proyecto (
    id_reporte integer NOT NULL,
    id_proyecto integer NOT NULL,
    id_usuario integer,
    motivo text,
    resuelto boolean DEFAULT false NOT NULL,
    fecha timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: reportes_proyecto_id_reporte_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reportes_proyecto_id_reporte_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: reportes_proyecto_id_reporte_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reportes_proyecto_id_reporte_seq OWNED BY public.reportes_proyecto.id_reporte;


--
-- Name: soporte; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.soporte (
    id_soporte bigint NOT NULL,
    usuario_id integer NOT NULL,
    asunto character varying(150) NOT NULL,
    descripcion text NOT NULL,
    estado character varying(30) DEFAULT 'pendiente'::character varying NOT NULL,
    fecha_creacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    respuesta text,
    fecha_respuesta timestamp without time zone,
    respondido_por integer,
    token_respuesta character varying(128)
);


--
-- Name: soporte_id_soporte_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.soporte ALTER COLUMN id_soporte ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.soporte_id_soporte_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: tipos_usuario; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tipos_usuario (
    id_tipo integer NOT NULL,
    nombre_tipo character varying(50) NOT NULL
);


--
-- Name: tipos_usuario_id_tipo_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tipos_usuario_id_tipo_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tipos_usuario_id_tipo_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tipos_usuario_id_tipo_seq OWNED BY public.tipos_usuario.id_tipo;


--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios (
    id_usuario integer NOT NULL,
    google_id character varying(255),
    nombre_completo character varying(100) NOT NULL,
    correo_usuario text NOT NULL,
    foto_perfil text,
    id_tipo integer,
    id_dominio integer,
    fecha_creacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    activo boolean DEFAULT true NOT NULL,
    grado character varying(10)
);


--
-- Name: usuarios_id_usuario_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usuarios_id_usuario_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuarios_id_usuario_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usuarios_id_usuario_seq OWNED BY public.usuarios.id_usuario;


--
-- Name: categorias id_categoria; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categorias ALTER COLUMN id_categoria SET DEFAULT nextval('public.categorias_id_categoria_seq'::regclass);


--
-- Name: documentos_proyecto id_documento; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_proyecto ALTER COLUMN id_documento SET DEFAULT nextval('public.documentos_proyecto_id_documento_seq'::regclass);


--
-- Name: dominios_permitidos id_dominio; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dominios_permitidos ALTER COLUMN id_dominio SET DEFAULT nextval('public.dominios_permitidos_id_dominio_seq'::regclass);


--
-- Name: etiquetas id_etiqueta; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etiquetas ALTER COLUMN id_etiqueta SET DEFAULT nextval('public.etiquetas_id_etiqueta_seq'::regclass);


--
-- Name: proyectos id_proyecto; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyectos ALTER COLUMN id_proyecto SET DEFAULT nextval('public.proyectos_id_proyecto_seq'::regclass);


--
-- Name: reportes_proyecto id_reporte; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reportes_proyecto ALTER COLUMN id_reporte SET DEFAULT nextval('public.reportes_proyecto_id_reporte_seq'::regclass);


--
-- Name: tipos_usuario id_tipo; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tipos_usuario ALTER COLUMN id_tipo SET DEFAULT nextval('public.tipos_usuario_id_tipo_seq'::regclass);


--
-- Name: usuarios id_usuario; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios ALTER COLUMN id_usuario SET DEFAULT nextval('public.usuarios_id_usuario_seq'::regclass);


--
-- Name: categorias categorias_nombre_categoria_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categorias
    ADD CONSTRAINT categorias_nombre_categoria_key UNIQUE (nombre_categoria);


--
-- Name: categorias categorias_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categorias
    ADD CONSTRAINT categorias_pkey PRIMARY KEY (id_categoria);


--
-- Name: configuracion configuracion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.configuracion
    ADD CONSTRAINT configuracion_pkey PRIMARY KEY (clave);


--
-- Name: documentos_proyecto documentos_proyecto_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_proyecto
    ADD CONSTRAINT documentos_proyecto_pkey PRIMARY KEY (id_documento);


--
-- Name: dominios_permitidos dominios_permitidos_dominio_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dominios_permitidos
    ADD CONSTRAINT dominios_permitidos_dominio_key UNIQUE (dominio);


--
-- Name: dominios_permitidos dominios_permitidos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dominios_permitidos
    ADD CONSTRAINT dominios_permitidos_pkey PRIMARY KEY (id_dominio);


--
-- Name: etiquetas etiquetas_nombre_etiqueta_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etiquetas
    ADD CONSTRAINT etiquetas_nombre_etiqueta_key UNIQUE (nombre_etiqueta);


--
-- Name: etiquetas etiquetas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.etiquetas
    ADD CONSTRAINT etiquetas_pkey PRIMARY KEY (id_etiqueta);


--
-- Name: permisos_rol permisos_rol_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permisos_rol
    ADD CONSTRAINT permisos_rol_pkey PRIMARY KEY (accion, rol);


--
-- Name: proyecto_colaboradores proyecto_colaboradores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyecto_colaboradores
    ADD CONSTRAINT proyecto_colaboradores_pkey PRIMARY KEY (id_proyecto, id_usuario);


--
-- Name: proyecto_likes proyecto_likes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyecto_likes
    ADD CONSTRAINT proyecto_likes_pkey PRIMARY KEY (id_proyecto, id_usuario);


--
-- Name: proyecto_valoraciones proyecto_valoraciones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyecto_valoraciones
    ADD CONSTRAINT proyecto_valoraciones_pkey PRIMARY KEY (id_proyecto, id_usuario);


--
-- Name: proyectos_etiquetas proyectos_etiquetas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyectos_etiquetas
    ADD CONSTRAINT proyectos_etiquetas_pkey PRIMARY KEY (id_proyecto, id_etiqueta);


--
-- Name: proyectos proyectos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyectos
    ADD CONSTRAINT proyectos_pkey PRIMARY KEY (id_proyecto);


--
-- Name: reportes_proyecto reportes_proyecto_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reportes_proyecto
    ADD CONSTRAINT reportes_proyecto_pkey PRIMARY KEY (id_reporte);


--
-- Name: soporte soporte_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.soporte
    ADD CONSTRAINT soporte_pkey PRIMARY KEY (id_soporte);


--
-- Name: soporte soporte_token_respuesta_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.soporte
    ADD CONSTRAINT soporte_token_respuesta_key UNIQUE (token_respuesta);


--
-- Name: tipos_usuario tipos_usuario_nombre_tipo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tipos_usuario
    ADD CONSTRAINT tipos_usuario_nombre_tipo_key UNIQUE (nombre_tipo);


--
-- Name: tipos_usuario tipos_usuario_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tipos_usuario
    ADD CONSTRAINT tipos_usuario_pkey PRIMARY KEY (id_tipo);


--
-- Name: usuarios usuarios_correo_usuario_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_correo_usuario_key UNIQUE (correo_usuario);


--
-- Name: usuarios usuarios_google_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_google_id_key UNIQUE (google_id);


--
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id_usuario);


--
-- Name: ix_soporte_estado_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_soporte_estado_fecha ON public.soporte USING btree (estado, fecha_creacion DESC);


--
-- Name: documentos_proyecto documentos_proyecto_id_proyecto_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documentos_proyecto
    ADD CONSTRAINT documentos_proyecto_id_proyecto_fkey FOREIGN KEY (id_proyecto) REFERENCES public.proyectos(id_proyecto) ON DELETE CASCADE;


--
-- Name: proyecto_colaboradores proyecto_colaboradores_id_proyecto_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyecto_colaboradores
    ADD CONSTRAINT proyecto_colaboradores_id_proyecto_fkey FOREIGN KEY (id_proyecto) REFERENCES public.proyectos(id_proyecto) ON DELETE CASCADE;


--
-- Name: proyecto_colaboradores proyecto_colaboradores_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyecto_colaboradores
    ADD CONSTRAINT proyecto_colaboradores_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuarios(id_usuario) ON DELETE CASCADE;


--
-- Name: proyecto_likes proyecto_likes_id_proyecto_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyecto_likes
    ADD CONSTRAINT proyecto_likes_id_proyecto_fkey FOREIGN KEY (id_proyecto) REFERENCES public.proyectos(id_proyecto) ON DELETE CASCADE;


--
-- Name: proyecto_likes proyecto_likes_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyecto_likes
    ADD CONSTRAINT proyecto_likes_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuarios(id_usuario) ON DELETE CASCADE;


--
-- Name: proyecto_valoraciones proyecto_valoraciones_id_proyecto_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyecto_valoraciones
    ADD CONSTRAINT proyecto_valoraciones_id_proyecto_fkey FOREIGN KEY (id_proyecto) REFERENCES public.proyectos(id_proyecto) ON DELETE CASCADE;


--
-- Name: proyecto_valoraciones proyecto_valoraciones_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyecto_valoraciones
    ADD CONSTRAINT proyecto_valoraciones_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuarios(id_usuario) ON DELETE CASCADE;


--
-- Name: proyectos_etiquetas proyectos_etiquetas_id_etiqueta_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyectos_etiquetas
    ADD CONSTRAINT proyectos_etiquetas_id_etiqueta_fkey FOREIGN KEY (id_etiqueta) REFERENCES public.etiquetas(id_etiqueta) ON DELETE CASCADE;


--
-- Name: proyectos_etiquetas proyectos_etiquetas_id_proyecto_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyectos_etiquetas
    ADD CONSTRAINT proyectos_etiquetas_id_proyecto_fkey FOREIGN KEY (id_proyecto) REFERENCES public.proyectos(id_proyecto) ON DELETE CASCADE;


--
-- Name: proyectos proyectos_id_categoria_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyectos
    ADD CONSTRAINT proyectos_id_categoria_fkey FOREIGN KEY (id_categoria) REFERENCES public.categorias(id_categoria) ON DELETE SET NULL;


--
-- Name: proyectos proyectos_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proyectos
    ADD CONSTRAINT proyectos_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuarios(id_usuario) ON DELETE CASCADE;


--
-- Name: reportes_proyecto reportes_proyecto_id_proyecto_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reportes_proyecto
    ADD CONSTRAINT reportes_proyecto_id_proyecto_fkey FOREIGN KEY (id_proyecto) REFERENCES public.proyectos(id_proyecto) ON DELETE CASCADE;


--
-- Name: reportes_proyecto reportes_proyecto_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reportes_proyecto
    ADD CONSTRAINT reportes_proyecto_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuarios(id_usuario) ON DELETE SET NULL;


--
-- Name: soporte soporte_respondido_por_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.soporte
    ADD CONSTRAINT soporte_respondido_por_fkey FOREIGN KEY (respondido_por) REFERENCES public.usuarios(id_usuario) ON DELETE SET NULL;


--
-- Name: soporte soporte_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.soporte
    ADD CONSTRAINT soporte_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id_usuario) ON DELETE CASCADE;


--
-- Name: usuarios usuarios_id_dominio_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_id_dominio_fkey FOREIGN KEY (id_dominio) REFERENCES public.dominios_permitidos(id_dominio) ON DELETE RESTRICT;


--
-- Name: usuarios usuarios_id_tipo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_id_tipo_fkey FOREIGN KEY (id_tipo) REFERENCES public.tipos_usuario(id_tipo) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

\unrestrict 0TDhDwqimImlRJtDMU7nTrCoPxi9w2BNUmDzC5190yyIvMTYxO4qSgebbLWwu8g

